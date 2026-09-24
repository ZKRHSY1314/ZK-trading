"""M2b P-D - offline tests. Remote connections are blocked for the whole process.

Blocks:
  A  plan mode and path/environment safety (F1-F8, arming refusal)
  B  S1: an end-to-end deadline that actually bounds reads, retries and decoding
  C  transport adaptation: exception mapping, response shape, pacing, stops
  D  P-B: the pure decoder, fail-closed on every malformed body
  E  S2: one deterministic outcome table, nine reproduced cases
  F  Section 6 checks, decidable on synthetic rows
  G  S3: frozen reference inputs and a replay that opens no production database
  H  R1: the adapter-replay harness
  I  redaction and cleanup
  J  closure round 2: the real call chains (B1-B5)
  K  closure round 3: evidence ownership after cancellation (R1), bounded
     finalization (R2), attempt reconciliation (R3), the BJ exception bound to the
     KLC history request (R4)

Real samples: the L-block drives the decoder with the TWO real vendor bodies retained by
boundary-1b run 20260908T021722Z, referenced by SHA-256 so a substituted file fails rather
than passes. They are the only real samples this project has, and they cover exactly two
symbols on one day: they establish that the decoder handles the real grammar, not that the
live path, the semantic checks or a three-year corpus are validated. `BJ920000` has never
been contacted, and no test here invents a body.

Run: python test_m2_smoke.py
"""

from __future__ import annotations

import atexit
import hashlib
import json
import os
import shutil
import socket
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

# Every module that will ever be needed is imported FIRST. `ssl.SSLSocket` subclasses
# `socket.socket` at import time, so blocking the class before these imports would break
# the import machinery rather than the network.
import ssl                                            # noqa: E402,F401
import requests                                       # noqa: E402
import pandas                                         # noqa: E402,F401
from akshare.stock import cons as _stock_cons         # noqa: E402,F401
from akshare.stock import stock_zh_a_sina as _stock_adapter    # noqa: E402
from akshare.index import index_stock_zh as _index_adapter     # noqa: E402

import sina_klc_decoder as dec                        # noqa: E402
import smoke_capture as cap                           # noqa: E402
import smoke_checks as chk                            # noqa: E402
import smoke_outcomes as out                          # noqa: E402
import transport as tp                                # noqa: E402

# ---- from here on no test may reach a remote host, for any reason -------------------
# Not a blanket `socket.socket` block: the JS engine the decoder runs on starts an
# asyncio loop whose self-pipe is a loopback socket pair on Windows, so blocking the
# class would break the adapter replay for a reason unrelated to the vendor. The guard
# refuses every connection to a non-loopback host, which is the property that matters.
_GUARD = cap.no_remote_connections("the M2b test suite attempted a network connection")
_GUARD.__enter__()

CASES = []
CONSTS = cap.adapter_constants()
PLANNED = cap.expected_requests(CONSTS)
SESSIONS, CALENDAR_SHA = chk.load_calendar(cap.CALENDAR)
WINDOW = [s for s in SESSIONS if cap.WINDOW_START <= s <= cap.WINDOW_END]
POST_BOUNDARY = [s for s in WINDOW if s >= cap.BJ_CODE_BOUNDARY]

#: A stand-in for the vendor routine. The hash pin is NEVER skipped: a test that supplies
#: its own routine must also supply that routine's true hash, so `decode_klc` still
#: refuses a routine whose hash does not match what the caller declared.
FAKE_ROUTINE = "function d(t){return []}"
FAKE_ROUTINE_SHA = hashlib.sha256(FAKE_ROUTINE.encode("utf-8")).hexdigest()

HTML = b"<html>NOT MARKET DATA</html>"

#: The command `scripts/run_stack.ps1:338` actually starts the API with. The pre-D2 regex
#: required the literal "backend" after "uvicorn", so it did not match this.
REAL_API_COMMAND = ("python.exe -X utf8 -m uvicorn app.main:app "
                    "--host 127.0.0.1 --port 8000")

#: A calendar that is byte-identical in meaning but not the approved pin, written once so
#: the EV4 regression can prove the pin is enforced rather than recorded.
_CAL_DIR = Path(tempfile.mkdtemp(prefix="m2b_cal_"))
REPO_CALENDAR_COPY = _CAL_DIR / "calendar.json"
REPO_CALENDAR_COPY.write_bytes(cap.CALENDAR.read_bytes() + b"\n")
atexit.register(lambda: shutil.rmtree(_CAL_DIR, ignore_errors=True))


def case(name):
    def deco(fn):
        CASES.append((name, fn))
        return fn
    return deco


# ------------------------------------------------------------------------ fixtures
class FakeRacer:
    """Returns the rows a payload is registered for; raises like a JS error otherwise."""

    def __init__(self, table):
        self.table = table

    def eval(self, code, **kwargs):
        self.code = code

    def call(self, name, payload, **kwargs):
        if payload not in self.table:
            raise RuntimeError("SyntaxError: the routine failed on this payload")
        return self.table[payload]


def payload_for(symbol):
    # "K2" is the 12-bit header 3466 -> branch O, the only branch that emits `amount`.
    return "K2" + symbol


def klc_body(symbol, instrument_class=None):
    """Use the REAL variable-name grammar: KLC_K2_ for stocks, KLC_KL_ for the index."""
    if instrument_class is None:
        instrument_class = "benchmark" if symbol == "sh000300" else "stock"
    name = dec.expected_js_variable("klc", instrument_class, symbol)
    return ('var %s="%s";' % (name, payload_for(symbol))).encode("utf-8")


def jsonp_body(symbol, series, *, shape="object", guard=True):
    """The auxiliary body. `shape="object"` is what the vendor really serves."""
    if shape == "object":
        inner = ",".join('{"date":"%s","amount":%s}' % (d, v) for d, v in series)
    else:
        inner = ",".join('["%s",%s]' % (d, v) for d, v in series)
    prefix = "/*<script>location.href='//sina.com';</script>*/\n" if guard else ""
    return ('%svar KKE_ShareAmount_%s=([%s]);'
            % (prefix, symbol, inner)).encode("utf-8")


def price_rows(dates, *, with_amount=True, base=10.0):
    rows = []
    for index, date in enumerate(dates):
        close = round(base + (index % 7) * 0.1, 2)
        volume = 1_000_000.0 + index
        row = {"date": date, "open": close, "high": round(close + 0.05, 2),
               "low": round(close - 0.05, 2), "close": close, "volume": volume}
        if with_amount:
            row["amount"] = round(close * volume, 2)
        rows.append(row)
    return rows


def reference_for(rows, klass):
    """The cache view of the same sessions: hands for stocks, same volume for an index."""
    out = []
    for row in rows:
        item = {"trade_date": row["date"], "close": row["close"],
                "volume": row["volume"] / (100.0 if klass == "stock" else 1.0),
                "amount": row.get("amount"),
                "source": "akshare.stock_zh_a_hist",
                "adjustment_mode": "qfq" if klass == "stock" else "none",
                "volume_unit": "hand" if klass == "stock" else "unknown",
                "quality_status": "ready", "updated_at": "2026-09-05T00:00:00Z"}
        out.append(item)
    return out


def build_extract(rows_by_symbol, symbols=None):
    rules = dict(cap.REFERENCE_RULES, sql="<frozen>",
                 symbols=symbols or [j["manifest_symbol"] for j in cap.JOBS],
                 window=[cap.WINDOW_START, cap.WINDOW_END])
    extract = {"schema": "m2b.reference_extract.v1", "rules": rules,
               "database_fingerprint": {"path": "<synthetic>", "exists": True},
               "rows": rows_by_symbol,
               "row_counts": {k: len(v) for k, v in rows_by_symbol.items()}}
    extract["content_sha256"] = cap.canonical_sha256(
        {"rules": rules, "rows": rows_by_symbol})
    return extract


def scenario(tmp, *, bj="pre", specs=None, run_status="completed", abort_reason=None,
             ref_rows=None, live_override=None, span=60):
    """A complete synthetic evidence tree plus everything `run_checks` needs."""
    tmp = Path(tmp)
    raw = tmp / "raw"
    raw.mkdir(parents=True, exist_ok=True)
    (tmp / "reference").mkdir(parents=True, exist_ok=True)

    bj_dates = WINDOW if bj == "pre" else POST_BOUNDARY
    live = {"sh600011": price_rows(WINDOW),
            "sh000300": price_rows(WINDOW, with_amount=False, base=3500.0),
            "bj920000": price_rows(bj_dates, base=7.0)}
    # The reference is frozen from the UNMODIFIED series, exactly as the cache would
    # already hold it: a defect injected into the live series must therefore show up as
    # a disagreement, not be mirrored into the reference and cancel itself out.
    base_live = {sym: [dict(r) for r in rows] for sym, rows in live.items()}
    if live_override:
        live = live_override(live)

    table = {payload_for(sym): rows for sym, rows in live.items()}
    shares = {sym: [(d, 250_000.0) for d in [r["date"] for r in rows]]
              for sym, rows in live.items()}

    bodies = {}
    for item in PLANNED:
        sym = item["symbol"]
        klass = next(j["instrument_class"] for j in cap.JOBS if j["job"] == item["job"])
        bodies[item["index"]] = (klc_body(sym, klass) if item["kind"] == "klc"
                                 else jsonp_body(sym, shares[sym]))

    if ref_rows is None:
        ref_rows = {"SH600011": reference_for(base_live["sh600011"][-span:], "stock"),
                    "SH000300": reference_for(base_live["sh000300"][-span:], "benchmark"),
                    "BJ920000": reference_for(base_live["bj920000"][-span:], "stock")}
    extract = build_extract(ref_rows)
    (tmp / "reference" / "reference_extract.json").write_text(
        json.dumps(extract, indent=2), encoding="utf-8")

    specs = dict(specs or {})
    records, attempts = [], []
    stamp = [100.0]

    def attempt(item, number, status, error=None):
        """One ACTUAL wire attempt, shaped exactly as the runner persists it (R3).

        The classification is derived the way the unchanged M2a transport derives it, so
        the fixture cannot produce a manifest whose status and `transport_outcome`
        disagree - which is exactly what the checks now reject.
        """
        entry = {"request_index": item["index"], "attempt_no": number,
                 "url": item["url"], "source": cap.SOURCE_KEY,
                 "started_at_monotonic": stamp[0],
                 "started_at_utc": "2026-09-07T01:00:%02dZ" % item["index"],
                 "finished_at_monotonic": stamp[0] + 0.1, "elapsed_sec": 0.1,
                 "status": status, "error": error, "waited_sec": 0.0}
        entry["transport_outcome"] = chk.expected_transport_outcome(entry)
        attempts.append(entry)
        stamp[0] += 2.0
        return entry

    for item in PLANNED:
        spec = specs.get(item["index"], {})
        outcome = spec.get("outcome", "ok")
        record = {"index": item["index"], "job": item["job"], "symbol": item["symbol"],
                  "kind": item["kind"], "requested_url": item["url"],
                  "source_key": cap.SOURCE_KEY, "started_at_monotonic": stamp[0],
                  "started_at_utc": "2026-09-07T01:00:%02dZ" % item["index"],
                  "outcome": outcome, "status": spec.get("status"), "attempt_count": 0}
        if outcome == "ok":
            body = spec.get("body", bodies[item["index"]])
            (raw / item["filename"]).write_bytes(body)
            text = body.decode("utf-8", errors="replace")
            state, _payload, _reason = out.classify_payload(
                body, item["kind"], encoding="utf-8", routine=FAKE_ROUTINE,
                routine_sha256=FAKE_ROUTINE_SHA,
                racer_factory=lambda: FakeRacer(table))
            record.update(status=200, served_url=item["url"], bytes=len(body),
                          body_sha256=hashlib.sha256(body).hexdigest(),
                          text_sha256=spec.get("text_sha256", dec.sha256_text(text)),
                          encoding="utf-8", apparent_encoding="utf-8", headers={},
                          elapsed_sec=0.1, raw_file=item["filename"],
                          payload_state=spec.get("payload_state", state),
                          attempt_count=1)
            attempt(item, 1, 200)
        elif outcome == "failed":
            status = spec.get("status")
            retryable = spec.get("retryable", False)
            record.update(error=spec.get("error", "failure"), retryable=retryable,
                          failure_kind=spec.get("failure_kind"))
            if retryable:
                # An exhausted retryable failure is THREE actual attempts, all retryable.
                for number in (1, 2, 3):
                    last = attempt(item, number, status,
                                   None if status is not None else "TimeoutError")
                record["attempt_count"] = 3
            else:
                last = attempt(item, 1, status,
                               None if status is not None else
                               ("TlsFailure" if spec.get("failure_kind") == "tls"
                                else "TransportError"))
                record["attempt_count"] = 1
            # The record's terminal fields ARE the final attempt's, as capture records
            # them; a spec may still override to build a deliberately inconsistent case.
            record["transport_outcome"] = spec.get("transport_outcome",
                                                   last["transport_outcome"])
        else:
            record["reason"] = spec.get("reason", "skipped by the outcome table")
            record["skip_scope"] = spec.get("skip_scope", out.SKIP_JOB_LOCAL)
        record["attempt_positions"] = [p for p, a in enumerate(attempts)
                                       if a["request_index"] == item["index"]]
        records.append(record)

    manifest = {"schema": "m2b.capture_manifest.v3", "run_id": "20260907T010000Z",
                "run_mode": "live_smoke", "started_at_utc": "2026-09-07T01:00:00Z",
                "finished_at_utc": "2026-09-07T01:05:00Z", "run_status": run_status,
                "abort_reason": abort_reason, "requests": records, "attempts": attempts,
                "attempt_count_transport": len(attempts),
                "attempt_timestamps_complete": True,
                "deadline": {"budget_sec": 900.0, "grace_sec": 45.0,
                             "elapsed_sec": 12.0, "remaining_sec": 888.0},
                "environment": {"adapter_constants": CONSTS,
                                "hk_js_decode_sha256": dec.HK_JS_DECODE_SHA256},
                "protected_before": {}, "protected_after": {},
                "invalidating_changes": [], "reported_changes": [], "run_valid": True,
                "reference_extract_sha256": extract["content_sha256"]}
    (tmp / "capture_manifest.json").write_text(json.dumps(manifest, indent=2),
                                               encoding="utf-8")
    return {"dir": tmp, "manifest": manifest, "extract": extract, "live": live,
            "racer": lambda: FakeRacer(table), "bodies": bodies, "table": table}


def fake_replay(bodies, calls):
    """A stand-in adapter: returns exactly the raw-decode dates, requesting only bodies."""
    out = {"_requested_urls": list(bodies)}
    for label, _kind, _func, _args in calls:
        dates = FAKE_REPLAY_DATES.get(label, [])
        out[label] = {"rows": len(dates), "first_date": dates[0] if dates else None,
                      "last_date": dates[-1] if dates else None, "dates": list(dates),
                      "columns": ["date", "open", "high", "low", "close", "volume",
                                  "amount"]}
    return out


FAKE_REPLAY_DATES = {}


def run(scene, *, racer_override=None, **kwargs):
    global FAKE_REPLAY_DATES
    FAKE_REPLAY_DATES = {job: [r["date"] for r in rows]
                         for job, rows in scene["live"].items()}
    kwargs.setdefault("replay_fn", fake_replay)
    return chk.run_checks(manifest=scene["manifest"], raw_dir=scene["dir"] / "raw",
                          reference_extract=scene["extract"], routine=FAKE_ROUTINE,
                          routine_sha256=FAKE_ROUTINE_SHA,
                          racer_factory=racer_override or scene["racer"], **kwargs)


def statuses(result, cid):
    return {c["symbol"]: c["status"] for c in result["deterministic"]["checks"]
            if c["id"] == cid}


def quiet_lister():
    return [{"pid": 1, "cmdline": "C:/Windows/explorer.exe"}]


def preflight(tmp, **kwargs):
    import requests

    kwargs.setdefault("process_lister", quiet_lister)
    kwargs.setdefault("requests_module", requests)
    kwargs.setdefault("out_root", Path(tmp) / "m2b_smoke_x")
    kwargs.setdefault("evidence_dir", Path(tmp) / "evidence_x")
    return cap.preflight(**kwargs)


def by_id(checks):
    return {c.id: c for c in checks}


# =============================================================== A: plan and safety
@case("A --plan writes nothing, creates nothing and opens no socket")
def _():
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        original = cap.TMP_ROOT
        cap.TMP_ROOT = d / "tmp"
        try:
            run_obj = cap.SmokeRun("20260907T010000Z", evidence_root=d / "ev")
            plan = run_obj.plan(process_lister=quiet_lister)
        finally:
            cap.TMP_ROOT = original
        assert plan["writes"] == []
        assert not (d / "tmp").exists() and not (d / "ev").exists()
        assert list(d.iterdir()) == []
        assert len(plan["requests"]) == 5


@case("A --plan lists the five installed-adapter URLs in job order")
def _():
    plan = cap.SmokeRun("20260907T010000Z").plan(process_lister=quiet_lister)
    urls = [item["url"] for item in plan["requests"]]
    assert [item["job"] for item in plan["requests"]] == [
        "sh600011", "sh600011", "sh000300", "bj920000", "bj920000"], plan["requests"]
    assert urls[2].endswith("/hisdata/klc_kl.js?d=2020_2_4"), urls[2]
    assert all(u.islower() or "KKE_ShareAmount" in u for u in urls)
    assert all("sh600011" in u or "sh000300" in u or "bj920000" in u for u in urls)


@case("A the derived URLs differ from the M2a templates (G4/G5 corrected, not reused)")
def _():
    import provenance as prov

    m2a = set(prov.expected_urls("SH000300", "benchmark"))
    live = {item["url"] for item in PLANNED if item["job"] == "sh000300"}
    assert not (m2a & live), "the M2a index template must not be reused live"
    assert all("hisdata_klc2" in u for u in m2a)
    assert all("hisdata/klc_kl.js" in u for u in live)


@case("A a malformed run_id is refused before anything is constructed")
def _():
    for bad in ("today", "20260907", "20260907T0100Z", ""):
        try:
            cap.SmokeRun(bad)
        except cap.SmokeError:
            continue
        raise AssertionError("run_id %r was accepted" % bad)


@case("A F6 refuses a pre-existing output root")
def _():
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        original = cap.TMP_ROOT
        cap.TMP_ROOT = d / "tmp"
        try:
            out = d / "tmp" / "m2b_smoke_x"
            out.mkdir(parents=True)
            checks, _ = preflight(d, out_root=out, evidence_dir=d / "ev")
        finally:
            cap.TMP_ROOT = original
        f6 = by_id(checks)["F6"]
        assert f6.status == "FAIL" and "already exists" in f6.detail, f6.detail


@case("A F6 refuses a pre-existing evidence directory")
def _():
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        original = cap.TMP_ROOT
        cap.TMP_ROOT = d / "tmp"
        try:
            evidence = d / "ev"
            evidence.mkdir()
            checks, _ = preflight(d, out_root=d / "tmp" / "m2b_smoke_x",
                                  evidence_dir=evidence)
        finally:
            cap.TMP_ROOT = original
        f6 = by_id(checks)["F6"]
        assert f6.status == "FAIL" and "evidence directory already exists" in f6.detail


@case("A F6 refuses an output root outside tmp/")
def _():
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        checks, _ = preflight(d, out_root=d / "elsewhere" / "run", evidence_dir=d / "ev")
        f6 = by_id(checks)["F6"]
        assert f6.status == "FAIL" and "is not inside" in f6.detail, f6.detail


@case("A F7 refuses a monkeypatched REQUESTS_CA_BUNDLE")
def _():
    with tempfile.TemporaryDirectory() as d:
        os.environ["REQUESTS_CA_BUNDLE"] = str(Path(d) / "attacker.pem")
        try:
            checks, _ = preflight(d)
        finally:
            os.environ.pop("REQUESTS_CA_BUNDLE", None)
        f7 = by_id(checks)["F7"]
        assert f7.status == "FAIL" and "REQUESTS_CA_BUNDLE is set" in f7.detail, f7.detail


@case("A F7 refuses a session whose verify is not True")
def _():
    import requests

    with tempfile.TemporaryDirectory() as d:
        session = requests.Session()
        session.verify = False
        checks, _ = preflight(d, session=session)
        f7 = by_id(checks)["F7"]
        assert f7.status == "FAIL" and "session.verify is False" in f7.detail, f7.detail


@case("A F5 refuses a session with library-level retries")
def _():
    class Retry:
        total = 3
        redirect = 0

    class Adapter:
        max_retries = Retry()

    class Session:
        adapters = {"https://": Adapter()}
        verify = True
        cert = None

        def merge_environment_settings(self, *a, **k):
            return {"verify": True}

    with tempfile.TemporaryDirectory() as d:
        checks, _ = preflight(d, session=Session())
        f5 = by_id(checks)["F5"]
        assert f5.status == "FAIL" and "library-level retries" in f5.detail, f5.detail


@case("A F8 refuses when a refresh loop is in the process inventory")
def _():
    def busy():
        return [{"pid": 42,
                 "cmdline": "python backend\\scripts\\market_history_refresh_loop.py"}]

    with tempfile.TemporaryDirectory() as d:
        checks, _ = preflight(d, process_lister=busy)
        f8 = by_id(checks)["F8"]
        assert f8.status == "FAIL" and "the user's action" in f8.detail, f8.detail


@case("A armed capture refuses on a failed pre-flight and writes nothing")
def _():
    import requests

    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        original = cap.TMP_ROOT
        cap.TMP_ROOT = d / "tmp"
        try:
            run_obj = cap.SmokeRun("20260907T010000Z", evidence_root=d / "ev")
            def busy():
                return [{"pid": 7, "cmdline": "python backend/scripts/x_loop.py"}]
            try:
                run_obj.capture(session=requests.Session(), requests_module=requests,
                                process_lister=busy,
                                reference_reader=lambda: build_extract({}))
            except cap.PreflightError as exc:
                assert "F8" in str(exc), str(exc)
            else:
                raise AssertionError("capture ran with a dirty pre-flight")
        finally:
            cap.TMP_ROOT = original
        assert not (d / "tmp").exists(), "a refused capture created its output root"


# ================================================================== B: S1 deadline
class Clock:
    def __init__(self, step=0.0):
        self.now = 0.0
        self.step = step

    def __call__(self):
        self.now += self.step
        return self.now

    def advance(self, seconds):
        self.now += seconds


@case("B a trickling response is cut off at the deadline, not waited out")
def _():
    clock = Clock()
    deadline = cap.Deadline(10.0, clock=clock)

    class Trickle:
        def iter_content(self, chunk_size):
            while True:
                clock.advance(1.0)                    # each chunk arrives inside the gap
                yield b"x" * 8

        def close(self):
            pass

    try:
        cap.read_body_streamed(Trickle(), deadline=deadline, max_bytes=1 << 20)
    except cap.DeadlineExceeded as exc:
        assert "cut off rather than waited out" in str(exc), str(exc)
    else:
        raise AssertionError("the trickling response was not stopped")


@case("B an oversized response is refused while it is still arriving")
def _():
    clock = Clock()
    deadline = cap.Deadline(1e6, clock=clock)

    class Flood:
        def iter_content(self, chunk_size):
            while True:
                yield b"y" * 1024

        def close(self):
            pass

    try:
        cap.read_body_streamed(Flood(), deadline=deadline, max_bytes=4096)
    except cap.BodyTooLarge as exc:
        assert "still arriving" in str(exc)
    else:
        raise AssertionError("the byte budget was not enforced")


@case("B a blocked in-flight call stops the run at the deadline; the worker is abandoned")
def _():
    import threading

    clock = Clock(step=1.0)
    deadline = cap.Deadline(3.0, clock=clock)
    release = threading.Event()
    entered = threading.Event()

    def blocked():
        entered.set()
        release.wait(30)
        return "should not be used"

    try:
        cap.supervise(blocked, deadline=deadline, poll_sec=0.01, name="blocked-call")
    except cap.DeadlineExceeded as exc:
        assert "abandoned (never killed)" in str(exc), str(exc)
    else:
        raise AssertionError("supervise waited for a blocked call")
    finally:
        release.set()
    assert entered.is_set()


@case("B a stuck decoder is bounded by the same supervisor")
def _():
    clock = Clock(step=1.0)
    deadline = cap.Deadline(2.0, clock=clock, label="decode")
    spinning = {"stop": False}

    def stuck():
        while not spinning["stop"]:
            pass

    try:
        cap.supervise(stuck, deadline=deadline, poll_sec=0.01, name="decoder")
    except cap.DeadlineExceeded:
        pass
    else:
        raise AssertionError("a stuck decoder was not bounded")
    finally:
        spinning["stop"] = True


@case("B retry backoff near the deadline starts no further attempt")
def _():
    clock = Clock()
    deadline = cap.Deadline(5.0, clock=clock)
    issued = []

    def flaky(url, *, timeout, allow_redirects):
        deadline.check("before-request")
        issued.append(url)
        clock.advance(3.0)
        raise TimeoutError("slow")

    paced = tp.PacedTransport(flaky, clock=clock, sleeper=lambda s: clock.advance(s),
                              min_interval=0.1, ceiling=15)
    try:
        paced.get_with_retries("https://example.invalid/a", source="sina")
    except (tp.TransportError, cap.DeadlineExceeded):
        pass
    assert len(issued) <= 2, issued
    try:
        paced.get("https://example.invalid/b", source="sina")
    except (tp.RunAborted, cap.DeadlineExceeded, tp.TransportError):
        pass
    assert "https://example.invalid/b" not in issued, "a request started after the deadline"


@case("B an expired deadline is sticky through the unchanged PacedTransport")
def _():
    clock = Clock()
    deadline = cap.Deadline(1.0, clock=clock)
    calls = []

    def dead(url, *, timeout, allow_redirects):
        calls.append(url)
        clock.advance(2.0)
        raise cap.DeadlineExceeded("budget spent")

    paced = tp.PacedTransport(dead, clock=clock, sleeper=lambda s: None,
                              min_interval=0.01, ceiling=15)
    for _ in range(2):
        try:
            paced.get("https://example.invalid/a", source="sina")
        except tp.RunAborted:
            pass
    assert len(calls) == 1, "the abort was not sticky: %r" % (calls,)
    assert paced.aborted_reason


@case("B an aborted run leaves partial evidence and issues no further request")
def _():
    import requests

    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        original = cap.TMP_ROOT
        cap.TMP_ROOT = d / "tmp"
        clock = Clock()
        try:
            run_obj = cap.SmokeRun("20260907T010000Z", evidence_root=d / "ev",
                                   clock=clock, sleeper=lambda s: clock.advance(s))
            seen = []

            class Factory:
                def __init__(self, session, *, deadline, requests_module, clock):
                    self.deadline = deadline

                def __call__(self, url, *, timeout, allow_redirects):
                    seen.append(url)
                    if len(seen) == 1:
                        clock.advance(2.0)
                        return cap.CapturedResponse(
                            status=200, text='var a="K2x";', url=url, headers={},
                            content=b'var a="K2x";', encoding="utf-8",
                            apparent_encoding="utf-8", requested_url=url)
                    raise cap.DeadlineExceeded("wall-clock cap reached")

            manifest = run_obj.capture(
                session=requests.Session(), requests_module=requests,
                process_lister=quiet_lister, transport_factory=Factory,
                supervise_jobs=False,
                reference_reader=lambda: build_extract({"SH600011": []}))
        finally:
            cap.TMP_ROOT = original
        assert manifest["run_status"] == "aborted", manifest["run_status"]
        assert len(seen) == 2, seen
        outcomes = [r["outcome"] for r in manifest["requests"]]
        assert outcomes.count("skipped") == 3, outcomes
        assert (run_obj.out_root / "capture_manifest.json").exists()
        assert (run_obj.out_root / "raw" / PLANNED[0]["filename"]).exists(), \
            "the first captured body did not survive the abort"


@case("B the deadline arithmetic uses the injected clock only")
def _():
    clock = Clock()
    deadline = cap.Deadline(10.0, clock=clock)
    assert not deadline.expired() and deadline.remaining() == 10.0
    clock.advance(9.5)
    assert not deadline.expired()
    clock.advance(1.0)
    assert deadline.expired()
    snapshot = deadline.snapshot()
    assert snapshot["grace_sec"] == cap.SHUTDOWN_GRACE_SEC


# ==================================================== C: transport adaptation
class FakeExceptions:
    class RequestException(Exception):
        pass

    class ConnectionError(RequestException):
        pass

    class Timeout(RequestException):
        pass

    class ConnectTimeout(ConnectionError, Timeout):
        pass

    class SSLError(ConnectionError):
        pass


class FakeRequestsModule:
    exceptions = FakeExceptions


class FakeHttpResponse:
    def __init__(self, status_code, body, url, headers=None):
        self.status_code = status_code
        self._body = body
        self.url = url
        self.headers = headers or {}
        self.encoding = "utf-8"

    def iter_content(self, chunk_size):
        yield self._body

    def close(self):
        pass

    @property
    def text(self):
        return self._body.decode("utf-8")

    @property
    def apparent_encoding(self):
        return "utf-8"


class FakeSession:
    def __init__(self, handler):
        self.handler = handler

    def get(self, url, timeout=None, allow_redirects=None, stream=None):
        return self.handler(url)


@case("C a 200 with status_code is recorded ok, not 'unexpected status 0'")
def _():
    clock = Clock()
    live = cap.LiveSinaTransport(
        FakeSession(lambda url: FakeHttpResponse(200, b'var a="K2x";', url)),
        deadline=cap.Deadline(100.0, clock=clock),
        requests_module=FakeRequestsModule, clock=clock)
    paced = tp.PacedTransport(live, clock=clock, sleeper=lambda s: None,
                              min_interval=0.01, ceiling=15)
    response = paced.get("https://example.invalid/a", source="sina")
    assert response.status == 200 and response.content == b'var a="K2x";'
    assert paced.attempts[0].outcome == "ok", paced.attempts[0]


@case("C requests' exceptions map to transient builtins, but TLS stays non-retryable")
def _():
    clock = Clock()
    for raised, expected in ((FakeExceptions.Timeout("read"), TimeoutError),
                             (FakeExceptions.ConnectTimeout("connect"), TimeoutError),
                             (FakeExceptions.ConnectionError("refused"), ConnectionError),
                             (FakeExceptions.SSLError("bad cert"), cap.TlsFailure)):
        def handler(url, exc=raised):
            raise exc

        live = cap.LiveSinaTransport(FakeSession(handler),
                                     deadline=cap.Deadline(100.0, clock=clock),
                                     requests_module=FakeRequestsModule, clock=clock)
        try:
            live("https://example.invalid/a", timeout=(1, 1), allow_redirects=False)
        except BaseException as exc:                  # noqa: BLE001
            assert isinstance(exc, expected), (type(raised), type(exc))
        else:
            raise AssertionError("no exception for %r" % raised)


@case("C a transient mapping is retried; any other exception is not")
def _():
    clock = Clock()
    for exc, retryable in ((TimeoutError("t"), True), (ConnectionError("c"), True),
                           (ValueError("parser bug"), False)):
        def boom(url, *, timeout, allow_redirects, exc=exc):
            raise exc

        paced = tp.PacedTransport(boom, clock=clock, sleeper=lambda s: None,
                                  min_interval=0.01, ceiling=15)
        try:
            paced.get("https://example.invalid/a", source="sina")
        except tp.TransportError as err:
            assert err.retryable is retryable, (exc, err.retryable)
        assert paced.attempts[-1].outcome == ("transient" if retryable else "error")


@case("C pacing, the ceiling and a 403 stop behave as M2a validated them")
def _():
    clock = Clock()
    waits = []
    paced = tp.PacedTransport(
        lambda url, *, timeout, allow_redirects: cap.CapturedResponse(
            status=200, text="", url=url, headers={}, content=b"x"),
        clock=clock, sleeper=lambda s: (waits.append(s), clock.advance(s)),
        min_interval=1.5, ceiling=2)
    paced.get("https://example.invalid/a", source="sina")
    paced.get("https://example.invalid/b", source="sina")
    assert waits and waits[0] >= 1.5, waits
    try:
        paced.get("https://example.invalid/c", source="sina")
    except tp.RunAborted as exc:
        assert "ceiling" in str(exc)
    else:
        raise AssertionError("the ceiling did not abort")


@case("C two consecutive failed jobs stop the run before the third job")
def _():
    import requests

    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        original = cap.TMP_ROOT
        cap.TMP_ROOT = d / "tmp"
        clock = Clock()
        try:
            run_obj = cap.SmokeRun("20260907T010000Z", evidence_root=d / "ev",
                                   clock=clock, sleeper=lambda s: clock.advance(s))
            seen = []

            class Factory:
                def __init__(self, session, *, deadline, requests_module, clock):
                    pass

                def __call__(self, url, *, timeout, allow_redirects):
                    seen.append(url)
                    clock.advance(2.0)
                    raise ConnectionError("refused")

            manifest = run_obj.capture(
                session=requests.Session(), requests_module=requests,
                process_lister=quiet_lister, transport_factory=Factory,
                supervise_jobs=False,
                reference_reader=lambda: build_extract({}))
        finally:
            cap.TMP_ROOT = original
        assert manifest["run_status"] == "aborted"
        assert "consecutive failed jobs" in manifest["abort_reason"]
        jobs_touched = {r["job"] for r in manifest["requests"] if r["outcome"] != "skipped"}
        assert "bj920000" not in jobs_touched, jobs_touched


# ================================================================== D: the decoder
@case("D markup, an empty body and a non-var body are all refused")
def _():
    for body, fragment in ((HTML, "markup"), (b"", "empty body"),
                           (b"nonsense", "does not start with 'var'"),
                           (b"   ", "blank")):
        try:
            dec.extract_payload(dec.bytes_to_text(body, "utf-8"))
        except dec.DecodeError as exc:
            assert fragment in str(exc), (body, str(exc))
        else:
            raise AssertionError("accepted %r" % body)


@case("D a JS evaluation failure is a decode error, never an empty result")
def _():
    try:
        dec.decode_klc(klc_body("sh600011"), "utf-8", routine=FAKE_ROUTINE,
                       expected_routine_sha256=FAKE_ROUTINE_SHA,
                       racer_factory=lambda: FakeRacer({}))
    except dec.DecodeError as exc:
        assert "JS routine failed" in str(exc), str(exc)
    else:
        raise AssertionError("a JS error produced a result")


@case("D a changed vendor routine is refused before it is evaluated")
def _():
    try:
        dec.decode_klc(klc_body("sh600011"), "utf-8", routine="function d(){}",
                       expected_routine_sha256=FAKE_ROUTINE_SHA,
                       racer_factory=lambda: FakeRacer({}))
    except dec.DecodeError as exc:
        assert "vendor routine changed" in str(exc), str(exc)
    else:
        raise AssertionError("an unpinned routine was evaluated")


@case("D zero rows, duplicate dates and unsorted dates are all refused")
def _():
    payload = payload_for("sh600011")
    body = klc_body("sh600011")
    rows = price_rows(WINDOW[:3])
    for table, fragment in (
            ({payload: []}, "zero rows"),
            ({payload: [rows[0], dict(rows[1], date=rows[0]["date"])]}, "duplicate dates"),
            ({payload: [rows[1], rows[0]]}, "strictly increasing")):
        try:
            dec.decode_klc(body, "utf-8", routine=FAKE_ROUTINE,
                           expected_routine_sha256=FAKE_ROUTINE_SHA,
                           racer_factory=lambda t=table: FakeRacer(t))
        except dec.DecodeError as exc:
            assert fragment in str(exc), (fragment, str(exc))
        else:
            raise AssertionError("accepted %s" % fragment)


@case("D a non-numeric or non-finite field is refused")
def _():
    payload = payload_for("sh600011")
    row = dict(price_rows(WINDOW[:1])[0], close="n/a")
    try:
        dec.decode_klc(klc_body("sh600011"), "utf-8", routine=FAKE_ROUTINE,
                       expected_routine_sha256=FAKE_ROUTINE_SHA,
                       racer_factory=lambda: FakeRacer({payload: [row]}))
    except dec.DecodeError as exc:
        assert "not numeric" in str(exc), str(exc)
    else:
        raise AssertionError("a non-numeric close was accepted")


@case("D the decoder branch is read from the header, independently of the routine")
def _():
    code, name = dec.header_branch(payload_for("sh600011"))
    assert (code, name) == (3466, "O"), (code, name)
    for prefix, expected in (("D0", None), ("HX", 1479)):
        code, _ = dec.header_branch(prefix + "junk")
        if expected is not None:
            assert code == expected, (prefix, code)


@case("D the adapter's positional extraction and a strict parse must agree")
def _():
    body = b'var klc="K2abc"; var other="ZZ";'
    try:
        dec.extract_payload(body.decode("utf-8"))
    except dec.DecodeError as exc:
        assert ("disagree" in str(exc) or "single quoted" in str(exc)
                or "unexpected trailing content" in str(exc)), str(exc)
    else:
        raise AssertionError("a two-assignment body was accepted")


@case("D a strict bytes-to-text failure is reported, never replaced")
def _():
    try:
        dec.bytes_to_text(b'var a="\xff\xfe";', "utf-8")
    except dec.DecodeError as exc:
        assert "do not decode" in str(exc)
    else:
        raise AssertionError("invalid bytes were silently replaced")


@case("D request #2/#5 is labelled outstanding_share_wan and never amount")
def _():
    series = dec.parse_outstanding_share(
        jsonp_body("sh600011", [("2024-01-02", 250000.0), ("2024-01-03", 250000.0)]),
        "utf-8")
    assert [r["outstanding_share_wan"] for r in series] == [250000.0, 250000.0]
    assert all("amount" not in r for r in series), series
    for bad in (b'var KKE_ShareAmount_sh600011=([]);',
                b'var KKE_ShareAmount_sh600011=([["2024-01-02",-1]]);', HTML):
        try:
            dec.parse_outstanding_share(bad, "utf-8")
        except dec.DecodeError:
            continue
        raise AssertionError("accepted %r" % bad)
    # A ZERO, by contrast, is a real vendor observation: kept, flagged, never dropped.
    zero = dec.parse_outstanding_share(
        b'var KKE_ShareAmount_bj920000=([["2015-03-06",0],["2015-10-27",1800]]);', "utf-8")
    assert [r["usable"] for r in zero] == [False, True], zero
    assert len(zero) == 2, "a zero observation was dropped instead of flagged"


@case("D a date with a time-of-day or a non-UTC offset is refused")
def _():
    import datetime as dt

    for value in (dt.datetime(2024, 8, 13, 9, 30, tzinfo=dt.timezone.utc),
                  dt.datetime(2024, 8, 13, tzinfo=dt.timezone(dt.timedelta(hours=8))),
                  "2024-13-99", "not-a-date"):
        try:
            dec._normalize_date(value)
        except dec.DecodeError:
            continue
        raise AssertionError("accepted %r" % (value,))
    assert dec._normalize_date("2024-08-13T00:00:00Z") == "2024-08-13"


# =========================================================== E: the outcome table
@case("E every outcome-table pair is distinct and unlisted pairs fail closed")
def _():
    keys = [(r["transport_state"], r["payload_state"]) for r in chk.OUTCOME_TABLE]
    assert len(keys) == len(set(keys)), "the table has duplicate keys"
    row = chk.lookup_outcome("teleported", "sideways")
    assert row["job_result"] == chk.JOB_FAILED and row["skip_remaining"]
    for state in ("exhausted_retryable", "transport_error", "redirect",
                  "non_retryable_status"):
        for payload in ("decoded", "markup", "not_applicable"):
            row = chk.lookup_outcome(state, payload)
            assert row["evidence_class"] != "vendor_explicit_absence_at_path", state
            assert row["job_result"] == chk.JOB_FAILED


@case("E only an explicit 404/410 can produce a vendor-absence finding")
def _():
    absent = [r for r in chk.OUTCOME_TABLE
              if r["evidence_class"] == "vendor_explicit_absence_at_path"]
    assert len(absent) == 1 and absent[0]["transport_state"] == "vendor_not_found"
    for record in ({"outcome": "failed", "status": 503, "retryable": True},
                   {"outcome": "failed", "status": None, "error": "timed out",
                    "retryable": True},
                   {"outcome": "ok", "status": 200}):
        state = chk.transport_state_of(record)
        assert state != "vendor_not_found", (record, state)


def _bj_case(specs, run_status="completed", abort_reason=None):
    with tempfile.TemporaryDirectory() as d:
        scene = scenario(d, specs=specs, run_status=run_status,
                         abort_reason=abort_reason)
        result = run(scene)
        det = result["deterministic"]
        return det["outcomes"], det["verdicts"], det["checks"]


@case("E BJ 404: an explicit absence, request #5 skipped, and a qualified verdict")
def _():
    outcomes, verdicts, checks = _bj_case({
        4: {"outcome": "failed", "status": 404, "error": "unexpected status 404"},
        5: {"outcome": "skipped"}})
    rows = outcomes["bj920000"]["requests"]
    assert rows[0]["evidence_class"] == "vendor_explicit_absence_at_path"
    assert rows[1]["request_result"] == "SKIPPED"
    assert verdicts["per_job"]["bj920000"] == chk.JOB_NOT_SERVED
    assert verdicts["capability"] == chk.CAPABILITY_PASS_BJ, verdicts
    assert verdicts["authorizes_pilot"] is False
    c2 = [c for c in checks if c["id"] == "C2"][0]
    assert c2["measured"]["cause"] == "not established", c2


@case("E BJ exhausted 503 stays a transport failure, never a capability PASS")
def _():
    outcomes, verdicts, _ = _bj_case({
        4: {"outcome": "failed", "status": 503, "retryable": True,
            "error": "server error 503"},
        5: {"outcome": "skipped"}})
    row = outcomes["bj920000"]["requests"][0]
    assert row["transport_state"] == "exhausted_retryable"
    assert row["evidence_class"] == "inconclusive_transport"
    assert verdicts["capability"] == chk.CAPABILITY_FAIL, verdicts


@case("E BJ timeout stays a transport failure")
def _():
    outcomes, verdicts, _ = _bj_case({
        4: {"outcome": "failed", "status": None, "retryable": True,
            "transport_outcome": "transient",
            "error": "transient transport error: request timed out"},
        5: {"outcome": "skipped"}})
    assert outcomes["bj920000"]["requests"][0]["transport_state"] == "exhausted_retryable"
    assert verdicts["capability"] == chk.CAPABILITY_FAIL


@case("E a TLS failure is a transport failure, not an absence")
def _():
    outcomes, verdicts, _ = _bj_case({
        4: {"outcome": "failed", "status": None, "retryable": False,
            "transport_outcome": "error",
            "error": "non-transient transport error: SSLError certificate verify failed"},
        5: {"outcome": "skipped"}})
    row = outcomes["bj920000"]["requests"][0]
    assert row["transport_state"] == "transport_error", row
    assert row["evidence_class"] == "inconclusive_transport", row
    assert verdicts["capability"] == chk.CAPABILITY_FAIL, verdicts


@case("E 403 and 429 abort the run and fail the capability unconditionally")
def _():
    for status in (403, 429):
        outcomes, verdicts, _ = _bj_case(
            {4: {"outcome": "failed", "status": status, "error": "vendor stop"},
             5: {"outcome": "skipped", "skip_scope": out.SKIP_RUN_GLOBAL}},
            run_status="aborted", abort_reason="vendor returned %d" % status)
        row = outcomes["bj920000"]["requests"][0]
        assert row["aborts_run"] and row["evidence_class"] == "run_aborted_vendor_stop"
        assert verdicts["capability"] == chk.CAPABILITY_FAIL, (status, verdicts)


@case("E an empty or HTML 200 body is inconclusive payload evidence")
def _():
    for body, expected in ((b"", "empty"), (HTML, "markup")):
        outcomes, verdicts, _ = _bj_case({4: {"outcome": "ok", "body": body},
                                          5: {"outcome": "skipped"}})
        row = outcomes["bj920000"]["requests"][0]
        assert row["payload_state"] == expected, (expected, row)
        assert row["evidence_class"] == "inconclusive_payload"
        assert verdicts["capability"] == chk.CAPABILITY_INCONCLUSIVE, verdicts


@case("E a malformed encoded payload is inconclusive decode evidence")
def _():
    outcomes, verdicts, _ = _bj_case(
        {4: {"outcome": "ok", "body": b'var klc_kl_bj920000="ZZunregistered";'},
         5: {"outcome": "skipped"}})
    row = outcomes["bj920000"]["requests"][0]
    assert row["payload_state"] == "undecodable", row
    assert row["evidence_class"] == "inconclusive_decode"
    assert verdicts["capability"] == chk.CAPABILITY_INCONCLUSIVE


@case("E valid pre-boundary BJ history is a PASS with its classification recorded")
def _():
    with tempfile.TemporaryDirectory() as d:
        scene = scenario(d, bj="pre")
        det = run(scene)["deterministic"]
        c2 = [c for c in det["checks"] if c["id"] == "C2"][0]
        assert c2["measured"]["classification"] == "pre_boundary_history_served", c2
        assert det["verdicts"]["per_job"]["bj920000"] == "PASS", det["verdicts"]
        assert det["verdicts"]["capability"] == chk.CAPABILITY_PASS, det["verdicts"]


@case("E valid post-boundary-only BJ history is a PASS with a different classification")
def _():
    with tempfile.TemporaryDirectory() as d:
        scene = scenario(d, bj="post")
        det = run(scene)["deterministic"]
        c2 = [c for c in det["checks"] if c["id"] == "C2"][0]
        assert c2["measured"]["classification"] == "post_boundary_only", c2
        assert c2["measured"]["cause"] == "not established"
        assert det["verdicts"]["capability"] == chk.CAPABILITY_PASS


@case("E the request count always agrees with the outcome table")
def _():
    with tempfile.TemporaryDirectory() as d:
        scene = scenario(d, specs={4: {"outcome": "failed", "status": 404},
                                   5: {"outcome": "skipped"}})
        det = run(scene)["deterministic"]
        t3 = [c for c in det["checks"] if c["id"] == "T3"][0]
        assert t3["status"] == "PASS", t3["detail"]
        assert t3["measured"]["issued"] == 4 and t3["measured"]["skipped"] == 1

    with tempfile.TemporaryDirectory() as d:
        # a request skipped with no trigger is a contradiction the check must catch
        scene = scenario(d, specs={5: {"outcome": "skipped"}})
        det = run(scene)["deterministic"]
        t3 = [c for c in det["checks"] if c["id"] == "T3"][0]
        assert t3["status"] == "FAIL" and "no earlier skip trigger" in t3["detail"], t3


# ==================================================== F: Section 6 check decidability
@case("F the happy path passes every required check on synthetic rows")
def _():
    with tempfile.TemporaryDirectory() as d:
        scene = scenario(d)
        det = run(scene)["deterministic"]
        failed = [c for c in det["checks"]
                  if c["kind"] == "required" and c["status"] != "PASS"]
        assert not failed, [(c["id"], c["symbol"], c["detail"]) for c in failed]
        assert det["verdicts"]["capability"] == chk.CAPABILITY_PASS


@case("F U2 reports the windowed unit and the all-rows unit separately")
def _():
    with tempfile.TemporaryDirectory() as d:
        def contaminate(live):
            extra = dict(live["sh600011"][-1])
            extra = dict(extra, date="2026-12-31", amount=extra["amount"] * 100.0)
            live["sh600011"] = live["sh600011"] + [extra]
            return live

        scene = scenario(d, live_override=contaminate)
        det = run(scene)["deterministic"]
        u2 = [c for c in det["checks"] if c["id"] == "U2" and c["symbol"] == "sh600011"][0]
        assert u2["status"] == "PASS" and u2["measured"]["windowed"] == "share", u2
        assert "all_rows" in u2["measured"] and "diverges" in u2["measured"]


@case("F I2 accepts a flat ratio and a single step, and refuses two steps")
def _():
    tol = 0.002
    flat, _ = chk.split_one_step([1.0] * 10, tol)
    assert flat == list(range(10))
    stepped, index = chk.split_one_step([0.9] * 4 + [1.0] * 6, tol)
    assert index == 4 and len(stepped) == 6, (stepped, index)
    two, _ = chk.split_one_step([0.8] * 3 + [0.9] * 3 + [1.0] * 4, tol)
    assert two is None
    short, _ = chk.split_one_step([0.9] * 8 + [1.0] * 2, tol)
    assert short is None, "a post-step segment shorter than 3 sessions must not pass"


@case("F I3 and U3 are decidable and refuse a wrong ratio")
def _():
    with tempfile.TemporaryDirectory() as d:
        scene = scenario(d)
        broken = {sym: [dict(r, volume=r["volume"] * 2.0) for r in rows]
                  for sym, rows in scene["extract"]["rows"].items()}
        rebind(scene, broken)
        det = run(scene)["deterministic"]
        assert statuses(det_result(det), "I3")["sh600011"] == "FAIL"


def rebind(scene, rows_by_symbol):
    """Replace the frozen reference AND the capture manifest's binding to it.

    Changing retained evidence without re-binding is itself a defect the checks now
    catch; the tests that are about something else therefore rebind explicitly, and a
    dedicated regression covers the unbound case.
    """
    extract = build_extract(rows_by_symbol)
    scene["extract"] = extract
    scene["manifest"]["reference_extract_sha256"] = extract["content_sha256"]
    return extract


def det_result(det):
    return {"deterministic": det}


@case("F an off-calendar in-window date fails D3")
def _():
    import datetime as dt

    session_set = set(SESSIONS)
    offday = None
    for index, day in enumerate(WINDOW[:-1]):
        candidate = (dt.date.fromisoformat(day) + dt.timedelta(days=1)).isoformat()
        if candidate not in session_set and candidate < WINDOW[index + 1]:
            offday, position = candidate, index
            break
    assert offday, "no off-calendar day inside the window"

    with tempfile.TemporaryDirectory() as d:
        def bend(live):
            rows = [dict(r) for r in live["sh600011"]]
            rows[position] = dict(rows[position], date=offday)
            live["sh600011"] = rows
            return live

        scene = scenario(d, live_override=bend)
        det = run(scene)["deterministic"]
        d3 = [c for c in det["checks"] if c["id"] == "D3" and c["symbol"] == "sh600011"][0]
        assert d3["status"] == "FAIL", d3


@case("F a stock body without amount fails D2; an index body without amount does not")
def _():
    with tempfile.TemporaryDirectory() as d:
        def strip(live):
            live["sh600011"] = [{k: v for k, v in r.items() if k != "amount"}
                                for r in live["sh600011"]]
            return live

        scene = scenario(d, live_override=strip)
        det = run(scene)["deterministic"]
        assert statuses(det_result(det), "D2")["sh600011"] == "FAIL"
        assert statuses(det_result(det), "D2")["sh000300"] == "PASS"


@case("F U4 is date-aligned and advisory")
def _():
    with tempfile.TemporaryDirectory() as d:
        scene = scenario(d)
        det = run(scene)["deterministic"]
        u4 = [c for c in det["checks"] if c["id"] == "U4" and c["symbol"] == "sh600011"][0]
        assert u4["kind"] == "advisory" and u4["status"] == "ADVISORY"
        assert u4["measured"]["aligned_rows"] > 0, u4
        assert u4["measured"]["rows_without_applicable_share"] == 0, u4
        assert u4["measured"]["exceeding"] == [], u4


@case("F B2 is derived from the installed adapter: qfq DIVIDES, hfq multiplies")
def _():
    facts = chk.adapter_basis_facts()
    assert facts["qfq_divides"] is True, facts
    assert facts["hfq_multiplies"] is True, facts
    assert facts["raw_branch_has_no_factor"] is True, facts


@case("F B1 fails if a factor endpoint ever appears in the request log")
def _():
    with tempfile.TemporaryDirectory() as d:
        scene = scenario(d)
        scene["manifest"]["requests"][0]["requested_url"] = (
            "https://finance.sina.com.cn/realstock/company/sh600011/qfq.js")
        det = run(scene)["deterministic"]
        b1 = [c for c in det["checks"] if c["id"] == "B1"][0]
        assert b1["status"] == "FAIL", b1


@case("F a mixed-basis reference makes I2/I3/U3 INCONCLUSIVE, never FAIL")
def _():
    with tempfile.TemporaryDirectory() as d:
        scene = scenario(d)
        rows = list(scene["extract"]["rows"]["SH600011"])
        rows[0] = dict(rows[0], adjustment_mode="hfq")
        rebind(scene, dict(scene["extract"]["rows"], SH600011=rows))
        det = run(scene)["deterministic"]
        for cid in ("I2", "I3", "U3"):
            found = [c for c in det["checks"]
                     if c["id"] == cid and c["symbol"] == "sh600011"][0]
            assert found["status"] == chk.INCONCLUSIVE, (cid, found)
            assert "mixes adjustment bases" in found["detail"], found
        assert det["verdicts"]["capability"] == chk.CAPABILITY_INCONCLUSIVE


@case("F too little overlap is INCONCLUSIVE with a stated reason")
def _():
    with tempfile.TemporaryDirectory() as d:
        scene = scenario(d, span=2)
        det = run(scene)["deterministic"]
        i2 = [c for c in det["checks"] if c["id"] == "I2" and c["symbol"] == "sh600011"][0]
        assert i2["status"] == chk.INCONCLUSIVE and "overlapping sessions" in i2["detail"]


@case("F a zero-denominator reference row is excluded, not divided by")
def _():
    with tempfile.TemporaryDirectory() as d:
        scene = scenario(d)
        rows = [dict(r, close=0.0) for r in scene["extract"]["rows"]["SH600011"]]
        rebind(scene, dict(scene["extract"]["rows"], SH600011=rows))
        det = run(scene)["deterministic"]
        i2 = [c for c in det["checks"] if c["id"] == "I2" and c["symbol"] == "sh600011"][0]
        assert i2["status"] == chk.INCONCLUSIVE, i2


@case("F a reference session missing from the live series fails coverage")
def _():
    with tempfile.TemporaryDirectory() as d:
        def drop(live):
            live["sh600011"] = live["sh600011"][:-1]
            return live

        scene = scenario(d, live_override=drop)
        det = run(scene)["deterministic"]
        c1 = [c for c in det["checks"] if c["id"] == "C1"][0]
        assert c1["status"] == "FAIL" and c1["measured"]["span_missing"], c1


@case("F R1 fails when the adapter emits a date the raw decode does not carry")
def _():
    with tempfile.TemporaryDirectory() as d:
        scene = scenario(d)

        def fabricating(bodies, calls):
            out = fake_replay(bodies, calls)
            if "sh600011" in out:
                out["sh600011"]["dates"] = out["sh600011"]["dates"] + ["2099-01-01"]
            return out

        det = run(scene, replay_fn=fabricating)["deterministic"]
        r1 = [c for c in det["checks"] if c["id"] == "R1" and c["symbol"] == "sh600011"][0]
        assert r1["status"] == "FAIL", r1


@case("F a retained body that no longer matches its hash fails EV1")
def _():
    with tempfile.TemporaryDirectory() as d:
        scene = scenario(d)
        (scene["dir"] / "raw" / PLANNED[0]["filename"]).write_bytes(b'var a="K2z";')
        det = run(scene)["deterministic"]
        ev1 = [c for c in det["checks"] if c["id"] == "EV1"][0]
        assert ev1["status"] == "FAIL", ev1


@case("F the bytes-to-text step is compared with the captured response.text")
def _():
    with tempfile.TemporaryDirectory() as d:
        scene = scenario(d, specs={1: {"outcome": "ok", "text_sha256": "0" * 64}})
        det = run(scene)["deterministic"]
        ev2 = [c for c in det["checks"] if c["id"] == "EV2" and c["symbol"] == "sh600011"][0]
        assert ev2["status"] == "FAIL" and "response.text" in ev2["detail"], ev2


# ================================================== G: S3, frozen reference + replay
@case("G replay reproduces the deterministic block after the mock cache changes")
def _():
    with tempfile.TemporaryDirectory() as d:
        scene = scenario(d)
        first = run(scene)
        (scene["dir"] / "checks.json").write_text(
            json.dumps({"deterministic": first["deterministic"],
                        "deterministic_sha256": first["deterministic_sha256"],
                        "run_meta": first["run_meta"]}, indent=2), encoding="utf-8")

        # The "current" cache moves on. The frozen extract does not.
        moved = {sym: [dict(r, close=float(r["close"]) * 1.37) for r in rows]
                 for sym, rows in scene["extract"]["rows"].items()}
        build_extract(moved)

        FAKE_REPLAY_DATES.update({job: [r["date"] for r in rows]
                                  for job, rows in scene["live"].items()})
        second = chk.replay(scene["dir"], replay_fn=fake_replay,
                            routine=FAKE_ROUTINE, routine_sha256=FAKE_ROUTINE_SHA,
                            racer_factory=scene["racer"])
        assert second["matches_stored"] is True, (second["stored_sha256"],
                                                  second["deterministic_sha256"])
        assert second["deterministic_sha256"] == first["deterministic_sha256"]


@case("G replay opens no production database")
def _():
    with tempfile.TemporaryDirectory() as d:
        scene = scenario(d)
        run(scene)
        opened = []
        import sqlite3

        original = sqlite3.connect

        def spy(*args, **kwargs):
            opened.append(args[0] if args else None)
            return original(*args, **kwargs)

        sqlite3.connect = spy
        try:
            FAKE_REPLAY_DATES.update({job: [r["date"] for r in rows]
                                      for job, rows in scene["live"].items()})
            chk.replay(scene["dir"], replay_fn=fake_replay, routine=FAKE_ROUTINE,
                       routine_sha256=FAKE_ROUTINE_SHA, racer_factory=scene["racer"])
        finally:
            sqlite3.connect = original
        assert opened == [], opened


@case("G db_guard refuses a database open outright")
def _():
    import sqlite3

    with cap.db_guard("test"):
        try:
            sqlite3.connect(":memory:")
        except cap.SmokeError:
            pass
        else:
            raise AssertionError("db_guard let a connection through")
    sqlite3.connect(":memory:").close()


@case("G run timestamps live outside the hashed block")
def _():
    with tempfile.TemporaryDirectory() as d:
        scene = scenario(d)
        first = run(scene)
        scene["manifest"]["finished_at_utc"] = "2027-01-01T00:00:00Z"
        second = run(scene)
        assert second["deterministic_sha256"] == first["deterministic_sha256"]
        assert second["run_meta"]["finished_at_utc"] != first["run_meta"]["finished_at_utc"]


@case("G the frozen extract records the fields and rules the checks consume")
def _():
    extract = build_extract({"SH600011": reference_for(price_rows(WINDOW[:3]), "stock")})
    row = extract["rows"]["SH600011"][0]
    for field in ("trade_date", "close", "volume", "amount", "source",
                  "adjustment_mode", "volume_unit", "quality_status", "updated_at"):
        assert field in row, field
    assert extract["rules"]["never_opened"] == "market_history.sqlite3"
    assert extract["content_sha256"] == build_extract(extract["rows"])["content_sha256"]


# ============================================================= H: the R1 harness
@case("H the replay harness serves only captured URLs and honours params")
def _():
    url = "https://finance.sina.com.cn/realstock/company/sh000300/hisdata/klc_kl.js"
    fake = chk._FakeRequests({url + "?d=2020_2_4": (b'var a="K2x";', "utf-8")})
    assert fake.get(url, params={"d": "2020_2_4"}).text == 'var a="K2x";'
    try:
        fake.get("https://finance.sina.com.cn/realstock/company/sh600011/qfq.js")
    except AssertionError as exc:
        assert "did not capture" in str(exc), str(exc)
    else:
        raise AssertionError("an uncaptured URL was served")


@case("H the replay blocks sockets and restores both adapter modules")
def _():
    import pandas as pd
    from akshare.index import index_stock_zh
    from akshare.stock import stock_zh_a_sina

    url = "https://example.invalid/probe"

    def probe(symbol):
        body = stock_zh_a_sina.requests.get(url).text
        try:
            socket.create_connection(("finance.sina.com.cn", 443), timeout=1)
        except AssertionError as exc:
            assert "must not reach the network" in str(exc), str(exc)
        else:
            raise AssertionError("a remote connection was possible during the replay")
        return pd.DataFrame({"date": ["2024-08-13"], "close": [float(len(body))]})

    saved_stock, saved_index = stock_zh_a_sina.requests, index_stock_zh.requests
    stock_zh_a_sina._m2b_probe = probe
    try:
        result = chk.adapter_replay({url: (b'var a="K2x";', "utf-8")},
                                    [("probe", "stock", "_m2b_probe", ("sh600011",))])
    finally:
        del stock_zh_a_sina._m2b_probe
    assert result["probe"]["rows"] == 1 and result["probe"]["first_date"] == "2024-08-13"
    assert result["_requested_urls"] == [url]
    assert stock_zh_a_sina.requests is saved_stock
    assert index_stock_zh.requests is saved_index


# ============================================================ I: redaction, cleanup
@case("I credential-bearing headers and proxy userinfo are redacted")
def _():
    headers = cap.redact_headers({"Authorization": "Bearer secret", "Cookie": "sid=1",
                                  "Proxy-Authorization": "Basic x", "Server": "nginx"})
    assert headers["Authorization"] == "<redacted>"
    assert headers["Cookie"] == "<redacted>"
    assert headers["Proxy-Authorization"] == "<redacted>"
    assert headers["Server"] == "nginx"
    assert cap.redact_url("http://user:pw@127.0.0.1:7892") == "http://<redacted>@127.0.0.1:7892"
    proxies = cap.redact_proxies({"https": "http://user:pw@127.0.0.1:7892"})
    assert "pw" not in proxies["https"], proxies


@case("I cleanup moves the evidence out of tmp/ and deletes the temporary root")
def _():
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        original = cap.TMP_ROOT
        cap.TMP_ROOT = d / "tmp"
        try:
            run_obj = cap.SmokeRun("20260907T010000Z", evidence_root=d / "ev")
            run_obj.out_root.mkdir(parents=True)
            (run_obj.out_root / "raw").mkdir()
            (run_obj.out_root / "raw" / "01.bin").write_bytes(b"body")
            (run_obj.out_root / "capture_manifest.json").write_text("{}", encoding="utf-8")
            (run_obj.out_root / "REPORT.md").write_text("# report", encoding="utf-8")
            record = run_obj.cleanup()
        finally:
            cap.TMP_ROOT = original
        assert not run_obj.out_root.exists()
        assert (run_obj.evidence_dir / "raw" / "01.bin").read_bytes() == b"body"
        report = (run_obj.evidence_dir / "REPORT.md").read_text(encoding="utf-8")
        assert "Output tree SHA-256" in report and "raw/01.bin" in report
        assert record["raw_retained"] is True


@case("I cleanup refuses to overwrite an existing evidence directory")
def _():
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        original = cap.TMP_ROOT
        cap.TMP_ROOT = d / "tmp"
        try:
            run_obj = cap.SmokeRun("20260907T010000Z", evidence_root=d / "ev")
            run_obj.out_root.mkdir(parents=True)
            run_obj.evidence_dir.mkdir(parents=True)
            try:
                run_obj.cleanup()
            except cap.SmokeError as exc:
                assert "existing evidence directory" in str(exc)
            else:
                raise AssertionError("cleanup overwrote an evidence directory")
        finally:
            cap.TMP_ROOT = original


@case("I the report states the verdict without any readiness claim")
def _():
    with tempfile.TemporaryDirectory() as d:
        scene = scenario(d)
        result = run(scene)
        report = chk.render_report(result, scene["manifest"])
        assert "capability" in report and "PASS" in report
        for forbidden in ("ready for production", "corpus is complete", "training"):
            assert forbidden not in report.lower() or "never" in report.lower()
        assert "makes no statement about corpus coverage" in report


@case("I the connection guard refuses a remote host and permits the engine's self-pipe")
def _():
    import py_mini_racer

    try:
        socket.create_connection(("finance.sina.com.cn", 443), timeout=1)
    except AssertionError as exc:
        assert "network connection" in str(exc), str(exc)
    else:
        raise AssertionError("a remote connection was possible inside the test suite")
    try:
        socket.getaddrinfo("finance.sina.com.cn", 443)
    except AssertionError:
        pass
    else:
        raise AssertionError("a remote name was resolvable inside the test suite")
    # The JS engine still starts, which is why the guard is connection-level.
    assert py_mini_racer.MiniRacer().eval("1+1") == 2


@case("I a failure class is never inferred from the message text")
def _():
    # "non-transient" contains "transient"; a substring rule classified TLS failures as
    # retryable network faults. The transport's own outcome decides instead.
    record = {"outcome": "failed", "status": None, "retryable": False,
              "transport_outcome": "error",
              "error": "non-transient transport error: SSLError"}
    assert chk.transport_state_of(record) == "transport_error", record
    assert chk.transport_state_of(
        dict(record, transport_outcome="transient")) == "exhausted_retryable"
    assert chk.transport_state_of(
        {"outcome": "failed", "status": None, "error": "non-transient anything"}
    ) == "transport_error"


@case("A --plan opens no database and reports the reference extract as planned")
def _():
    with cap.db_guard("plan mode must not open a database"):
        plan = cap.SmokeRun("20260907T010000Z").plan(process_lister=quiet_lister)
    f2 = [c for c in plan["preflight"] if c["id"] == "F2"][0]
    assert f2["status"] == "PASS" and "PLANNED" in f2["detail"], f2
    assert f2["data"]["planned_window"] == [cap.WINDOW_START, cap.WINDOW_END]
    assert plan["budget"]["ceiling"] == 15
    assert plan["budget"]["wall_clock_cap_sec"] == 15 * 60.0
    assert plan["budget"]["consecutive_failed_jobs_stop"] == 2


@case("F R1 fails if the adapter requests a URL the smoke did not capture")
def _():
    with tempfile.TemporaryDirectory() as d:
        scene = scenario(d)

        def wandering(bodies, calls):
            out = fake_replay(bodies, calls)
            out["_requested_urls"] = list(bodies) + [
                "https://finance.sina.com.cn/realstock/company/sh600011/qfq.js"]
            return out

        det = run(scene, replay_fn=wandering)["deterministic"]
        r1 = [c for c in det["checks"] if c["id"] == "R1urls"][0]
        assert r1["status"] == "FAIL" and "qfq.js" in str(r1["detail"]), r1


@case("E every outcome-table state pair is reachable and reported")
def _():
    seen = set()
    for state in ("ok", "vendor_not_found", "vendor_stop", "exhausted_retryable",
                  "non_retryable_status", "redirect", "transport_error", "aborted",
                  "skipped"):
        for payload in ("decoded", "markup", "empty", "undecodable", "no_rows",
                        "not_applicable"):
            row = chk.lookup_outcome(state, payload)
            seen.add((row["job_result"], row["evidence_class"]))
            assert row["note"], (state, payload)
    assert (chk.JOB_CONTINUE, "decoded_payload") in seen
    assert (chk.JOB_NOT_SERVED, "vendor_explicit_absence_at_path") in seen
    assert (chk.JOB_FAILED, "run_aborted_vendor_stop") in seen



# ===================== J: closure regressions through the REAL call chains ===========
# Every case below drives the actual `SmokeRun -> TimedTransport -> PacedTransport ->
# LiveSinaTransport` chain, or the actual `run_checks` / `run_pipeline` path. A helper
# passing in isolation is not evidence that the integration behaves; that was the whole
# finding of the 1a review.

class _Restore:
    def __init__(self, **attrs):
        self.attrs = attrs
        self.saved = {}

    def __enter__(self):
        for name, value in self.attrs.items():
            self.saved[name] = getattr(cap, name)
            setattr(cap, name, value)
        return self

    def __exit__(self, *exc):
        for name, value in self.saved.items():
            setattr(cap, name, value)
        return False


def synthetic_preflight(extract):
    """Only the pre-flight and the production fingerprints are faked; capture is real."""
    data = {"reference_extract": extract, "protected_before": {},
            "adapter_constants": CONSTS,
            "hk_js_decode_sha256": dec.HK_JS_DECODE_SHA256}
    return _Restore(preflight=lambda **kw: ([cap.Check("fixture", "PASS", "synthetic")],
                                            data),
                    protected_fingerprints=lambda: {},
                    compare_fingerprints=lambda a, b: ([], []))


def capture_scene(root, scene, handler, *, clock=None, supervise_jobs=False):
    clock = clock or Clock()
    run = cap.SmokeRun("20260907T010000Z", out_root=Path(root) / "capture",
                       evidence_root=Path(root) / "evidence", clock=clock,
                       sleeper=clock.advance)
    with synthetic_preflight(scene["extract"]):
        manifest = run.capture(session=FakeSession(handler), requests_module=requests,
                               supervise_jobs=supervise_jobs, routine=FAKE_ROUTINE,
                               routine_sha256=FAKE_ROUTINE_SHA,
                               racer_factory=scene["racer"])
    return run, manifest, clock


def wire_handler(scene, *, override=None, seen=None):
    by_url = {item["url"]: item for item in PLANNED}

    def handler(url):
        item = by_url[url]
        if seen is not None:
            seen.append(item["index"])
        if override and item["index"] in override:
            return override[item["index"]](item)
        return FakeHttpResponse(200, scene["bodies"][item["index"]], url)

    return handler


def check_captured(run, manifest, scene, **kwargs):
    global FAKE_REPLAY_DATES
    FAKE_REPLAY_DATES = {job: [r["date"] for r in rows]
                         for job, rows in scene["live"].items()}
    kwargs.setdefault("replay_fn", fake_replay)
    return chk.run_checks(manifest=manifest, raw_dir=run.out_root / "raw",
                          reference_extract=scene["extract"], routine=FAKE_ROUTINE,
                          routine_sha256=FAKE_ROUTINE_SHA,
                          racer_factory=scene["racer"], **kwargs)


@case("J-B1 an already-spent run deadline stops the checks before the replay is entered")
def _():
    with tempfile.TemporaryDirectory() as d:
        scene = scenario(d)
        scene["manifest"]["deadline"] = {"budget_sec": 0.01, "grace_sec": 0.01,
                                         "elapsed_sec": 1000.0, "remaining_sec": -999.99}
        entered = []

        def never(bodies, calls):
            entered.append(True)
            return fake_replay(bodies, calls)

        try:
            run(scene, replay_fn=never)
        except cap.DeadlineExceeded as exc:
            assert "already spent" in str(exc), str(exc)
        else:
            raise AssertionError("the checks ran past an exhausted run deadline")
        assert entered == [], "the installed-adapter replay was entered after expiry"


@case("J-B1 a blocked adapter replay is bounded on the real run_checks path")
def _():
    import threading

    with tempfile.TemporaryDirectory() as d:
        scene = scenario(d)
        now = {"t": 0.0}
        entered, release = threading.Event(), threading.Event()

        def blocking(bodies, calls):
            entered.set()
            now["t"] = 10_000.0          # the budget is spent while we are inside it
            release.wait(10)
            return fake_replay(bodies, calls)

        try:
            run(scene, replay_fn=blocking,
                deadline=cap.Deadline(60.0, clock=lambda: now["t"], label="test"))
        except cap.DeadlineExceeded as exc:
            assert "abandoned (never killed)" in str(exc) or "deadline" in str(exc)
        else:
            raise AssertionError("a blocked replay was waited on indefinitely")
        finally:
            release.set()
        assert entered.is_set(), "the test did not actually reach the replay"


@case("J-B1 a decoder that will not return is bounded on the real check path")
def _():
    import threading

    with tempfile.TemporaryDirectory() as d:
        scene = scenario(d)
        now = {"t": 0.0}
        release = threading.Event()

        class Spinning(FakeRacer):
            def call(self, name, payload, **kwargs):
                now["t"] = 10_000.0      # the budget is spent inside the decoder
                release.wait(10)
                return super().call(name, payload, **kwargs)

        try:
            run(scene, racer_override=lambda: Spinning(scene["table"]),
                deadline=cap.Deadline(60.0, clock=lambda: now["t"], label="test"))
        except cap.DeadlineExceeded:
            pass
        else:
            raise AssertionError("a stuck decoder was not bounded inside run_checks")
        finally:
            release.set()


@case("J-B1 the pipeline captures, checks, reports and retains under ONE deadline")
def _():
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        scene = scenario(d / "scene")
        clock = Clock()
        run_obj = cap.SmokeRun("20260907T010000Z", out_root=d / "capture",
                               evidence_root=d / "evidence", clock=clock,
                               sleeper=clock.advance)
        global FAKE_REPLAY_DATES
        FAKE_REPLAY_DATES = {job: [r["date"] for r in rows]
                             for job, rows in scene["live"].items()}
        with synthetic_preflight(scene["extract"]):
            record = run_obj.run_pipeline(
                session=FakeSession(wire_handler(scene)), requests_module=requests,
                supervise_jobs=False, routine=FAKE_ROUTINE,
                routine_sha256=FAKE_ROUTINE_SHA, racer_factory=scene["racer"],
                replay_fn=fake_replay, plan_text="synthetic plan")
        assert record["phase"] == "done", record
        assert record["run_status"] == "completed", record
        assert record["capability"] == chk.CAPABILITY_PASS, record
        evidence = run_obj.evidence_dir
        for name in ("capture_manifest.json", "checks.json", "REPORT.md", "plan.txt"):
            assert (evidence / name).exists(), name
        assert (evidence / "raw").is_dir() and (evidence / "reference").is_dir()
        assert not run_obj.out_root.exists(), "the temporary root was not removed"
        assert "Output tree SHA-256" in (evidence / "REPORT.md").read_text(encoding="utf-8")


@case("J-B1 an exhausted deadline still reports and retains partial evidence")
def _():
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        scene = scenario(d / "scene")
        clock = Clock()
        run_obj = cap.SmokeRun("20260907T010000Z", out_root=d / "capture",
                               evidence_root=d / "evidence", clock=clock,
                               sleeper=clock.advance)

        by_url = {item["url"]: item for item in PLANNED}

        def slow(url):
            clock.advance(500.0)         # each request eats most of the 900 s budget
            return FakeHttpResponse(200, scene["bodies"][by_url[url]["index"]], url)

        with synthetic_preflight(scene["extract"]):
            record = run_obj.run_pipeline(
                session=FakeSession(slow), requests_module=requests,
                supervise_jobs=False, routine=FAKE_ROUTINE,
                routine_sha256=FAKE_ROUTINE_SHA, racer_factory=scene["racer"],
                replay_fn=fake_replay)
        assert record["run_status"] == "aborted", record
        assert record["capability"] == "INCONCLUSIVE", record
        # The SAME deadline object flowed from capture into the checks, so the phases
        # share one budget rather than each starting a fresh one.
        assert "deadline" in (record["error"] or "") and "expired" in record["error"], record
        assert "checks:" in record["error"], record
        assert (run_obj.evidence_dir / "REPORT.md").exists()
        assert (run_obj.evidence_dir / "capture_manifest.json").exists()
        assert (run_obj.evidence_dir / "raw").is_dir(), "partial evidence was lost"
        kept = sorted(p.name for p in (run_obj.evidence_dir / "raw").iterdir())
        assert kept, "no captured body survived the aborted run"
        assert not run_obj.out_root.exists()


@case("J-B1 no write can race finalization after the capture is closed")
def _():
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        scene = scenario(d / "scene")
        run_obj, manifest, _clock = capture_scene(d, scene, wire_handler(scene))
        assert run_obj.cancelled is True
        stored = (run_obj.out_root / "capture_manifest.json").read_bytes()
        for late in (lambda: run_obj._flush(run_obj._state, "x", {}),
                     lambda: run_obj._record(PLANNED[0], {"outcome": "ok"})):
            try:
                late()
            except cap.SmokeError as exc:
                assert "finalized" in str(exc), str(exc)
            else:
                raise AssertionError("a late write was accepted after finalization")
        assert (run_obj.out_root / "capture_manifest.json").read_bytes() == stored


@case("J-B2 HTML on the first request stops the job before its dependent request")
def _():
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        scene = scenario(d / "scene")
        seen = []
        handler = wire_handler(
            scene, seen=seen,
            override={1: lambda item: FakeHttpResponse(200, HTML, item["url"])})
        run_obj, manifest, _clock = capture_scene(d, scene, handler)
        assert 2 not in seen, "the dependent request was issued after an HTML payload"
        record = manifest["requests"][0]
        assert record["payload_state"] == "markup", record
        assert manifest["requests"][1]["outcome"] == "skipped"
        assert manifest["requests"][1]["skip_scope"] == out.SKIP_JOB_LOCAL
        det = check_captured(run_obj, manifest, scene)["deterministic"]
        t3 = [c for c in det["checks"] if c["id"] == "T3"][0]
        assert t3["status"] == "PASS", t3["detail"]
        assert det["job_results"]["sh600011"] == chk.JOB_INCONCLUSIVE_PAYLOAD


@case("J-B2 an empty 200 and a malformed KLC body stop their jobs the same way")
def _():
    for body, expected in ((b"", "empty"), (b'var klc_kl_sh600011="ZZnope";',
                                            "undecodable")):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            scene = scenario(d / "scene")
            seen = []
            handler = wire_handler(
                scene, seen=seen,
                override={1: lambda item, b=body: FakeHttpResponse(200, b, item["url"])})
            run_obj, manifest, _clock = capture_scene(d, scene, handler)
            assert 2 not in seen, (expected, seen)
            assert manifest["requests"][0]["payload_state"] == expected, manifest["requests"][0]
            det = check_captured(run_obj, manifest, scene)["deterministic"]
            assert [c for c in det["checks"] if c["id"] == "T3"][0]["status"] == "PASS"
            assert det["verdicts"]["capability"] == chk.CAPABILITY_INCONCLUSIVE


@case("J-B2 two payload-failed jobs stop the run before the third job is called")
def _():
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        scene = scenario(d / "scene")
        seen = []
        handler = wire_handler(
            scene, seen=seen,
            override={1: lambda item: FakeHttpResponse(200, HTML, item["url"]),
                      3: lambda item: FakeHttpResponse(200, HTML, item["url"])})
        run_obj, manifest, _clock = capture_scene(d, scene, handler)
        assert seen == [1, 3], seen
        assert manifest["run_status"] == "aborted", manifest["run_status"]
        assert "consecutive failed jobs" in manifest["abort_reason"]
        bj = [r for r in manifest["requests"] if r["job"] == "bj920000"]
        assert all(r["outcome"] == "skipped" for r in bj), bj
        assert all(r["skip_scope"] == out.SKIP_RUN_GLOBAL for r in bj), bj
        det = check_captured(run_obj, manifest, scene)["deterministic"]
        t3 = [c for c in det["checks"] if c["id"] == "T3"][0]
        assert t3["status"] == "PASS", t3["detail"]
        assert det["verdicts"]["capability"] != chk.CAPABILITY_PASS


@case("J-B3 a real requests SSLError is non-retryable and classified as a TLS failure")
def _():
    clock = Clock()
    seen = []

    def tls(url):
        seen.append(url)
        raise requests.exceptions.SSLError("synthetic certificate verification failure")

    live = cap.LiveSinaTransport(FakeSession(tls), deadline=cap.Deadline(100, clock=clock),
                                 requests_module=requests, clock=clock)
    paced = tp.PacedTransport(live, clock=clock, sleeper=clock.advance,
                              min_interval=1.5, ceiling=15)
    try:
        paced.get_with_retries(PLANNED[0]["url"], source="sina")
    except tp.TransportError as exc:
        assert exc.retryable is False, "a TLS failure was retried"
    else:
        raise AssertionError("no error raised for a TLS failure")
    assert len(seen) == 1, "the TLS failure was attempted %d times" % len(seen)
    assert [a.outcome for a in paced.attempts] == ["error"], paced.attempts
    record = {"outcome": "failed", "status": None, "retryable": False,
              "transport_outcome": "error", "failure_kind": "tls"}
    assert chk.transport_state_of(record) == "tls_failure"
    assert chk.lookup_outcome("tls_failure")["job_result"] == chk.JOB_FAILED


@case("J-B3 a known 403/429 is latched from the headers even if the body then fails")
def _():
    for status in (403, 429):
        clock = Clock()
        calls = []

        class StopWithBrokenBody(FakeHttpResponse):
            def iter_content(self, chunk_size):
                raise requests.exceptions.Timeout("body timeout after stop headers")
                yield b""

        def handler(url, code=status):
            calls.append(url)
            return StopWithBrokenBody(code, b"", url)

        live = cap.LiveSinaTransport(FakeSession(handler),
                                     deadline=cap.Deadline(100, clock=clock),
                                     requests_module=requests, clock=clock)
        paced = tp.PacedTransport(live, clock=clock, sleeper=clock.advance,
                                  min_interval=1.5, ceiling=15)
        try:
            paced.get_with_retries(PLANNED[0]["url"], source="sina")
        except tp.RunAborted as exc:
            assert str(status) in str(exc), str(exc)
        else:
            raise AssertionError("%d did not abort the run" % status)
        assert len(calls) == 1, "%d was retried %d times" % (status, len(calls))
        assert paced.aborted_reason, "the abort latch is still empty for %d" % status
        assert [a.outcome for a in paced.attempts] == ["stop"], paced.attempts


@case("J-B3 a failed non-200 attempt still retains bounded evidence")
def _():
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        scene = scenario(d / "scene")
        handler = wire_handler(scene, override={
            1: lambda item: FakeHttpResponse(404, b"not found", item["url"],
                                             {"Server": "nginx"})})
        run_obj, manifest, _clock = capture_scene(d, scene, handler)
        record = manifest["requests"][0]
        assert record["outcome"] == "failed" and record["status"] == 404, record
        assert record.get("raw_file"), "no bounded body was retained for a 404"
        assert record["headers"].get("Server") == "nginx", record["headers"]
        assert (run_obj.out_root / "raw" / record["raw_file"]).read_bytes() == b"not found"


@case("J-B4 recorded attempt starts are the actual wire starts, and T3 passes")
def _():
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        scene = scenario(d / "scene")
        clock = Clock()
        wire = []
        by_url = {item["url"]: item for item in PLANNED}

        def handler(url):
            wire.append(round(clock(), 6))
            return FakeHttpResponse(200, scene["bodies"][by_url[url]["index"]], url)

        run_obj, manifest, _clock = capture_scene(d, scene, handler, clock=clock)
        recorded = [a["started_at_monotonic"] for a in manifest["attempts"]]
        assert recorded == wire, (recorded, wire)
        assert all(b - a >= cap.MIN_INTERVAL for a, b in zip(wire, wire[1:])), wire
        det = check_captured(run_obj, manifest, scene)["deterministic"]
        t3 = [c for c in det["checks"] if c["id"] == "T3"][0]
        assert t3["status"] == "PASS", t3["detail"]
        assert det["verdicts"]["capability"] == chk.CAPABILITY_PASS, det["verdicts"]


@case("J-B4 a genuinely unpaced attempt fails T3")
def _():
    with tempfile.TemporaryDirectory() as d:
        scene = scenario(d)
        scene["manifest"]["attempts"][1]["started_at_monotonic"] = (
            scene["manifest"]["attempts"][0]["started_at_monotonic"] + 0.2)
        det = run(scene)["deterministic"]
        t3 = [c for c in det["checks"] if c["id"] == "T3"][0]
        assert t3["status"] == "FAIL" and "pacing violated" in t3["detail"], t3


@case("J-B4 a manifest without complete attempt timestamps cannot validate pacing")
def _():
    with tempfile.TemporaryDirectory() as d:
        scene = scenario(d)
        scene["manifest"]["attempt_timestamps_complete"] = False
        det = run(scene)["deterministic"]
        t3 = [c for c in det["checks"] if c["id"] == "T3"][0]
        assert t3["status"] == "FAIL" and "wire-start timestamp" in t3["detail"], t3


@case("J-B5 an explicitly invalidated capture can never PASS")
def _():
    with tempfile.TemporaryDirectory() as d:
        scene = scenario(d)
        scene["manifest"].update(run_valid=False,
                                 invalidating_changes=["production DB changed"])
        det = run(scene)["deterministic"]
        ev0 = [c for c in det["checks"] if c["id"] == "EV0"][0]
        assert ev0["status"] == "FAIL" and "production DB changed" in ev0["detail"], ev0
        assert det["verdicts"]["capability"] == chk.CAPABILITY_FAIL, det["verdicts"]


@case("J-B5 a missing capture envelope is missing evidence, not a pass")
def _():
    for field in ("run_valid", "protected_after", "deadline", "invalidating_changes"):
        with tempfile.TemporaryDirectory() as d:
            scene = scenario(d)
            scene["manifest"].pop(field)
            if field == "deadline":
                # No recorded budget: the checks still run, but EV0 records the gap.
                det = run(scene)["deterministic"]
            else:
                det = run(scene)["deterministic"]
            ev0 = [c for c in det["checks"] if c["id"] == "EV0"][0]
            assert ev0["status"] == "FAIL", (field, ev0)
            assert det["verdicts"]["capability"] == chk.CAPABILITY_FAIL, (field, det["verdicts"])


@case("J-B5 reference hashes are recomputed and bound to the capture manifest")
def _():
    with tempfile.TemporaryDirectory() as d:
        scene = scenario(d)
        scene["manifest"]["reference_extract_sha256"] = "0" * 64
        scene["extract"]["content_sha256"] = "f" * 64
        det = run(scene)["deterministic"]
        ev3 = [c for c in det["checks"] if c["id"] == "EV3"][0]
        assert ev3["status"] == "FAIL", ev3
        assert "does not match its content" in ev3["detail"], ev3
        assert det["verdicts"]["capability"] == chk.CAPABILITY_FAIL


@case("J-B5 altered retained reference content changes the deterministic hash")
def _():
    with tempfile.TemporaryDirectory() as d:
        scene = scenario(d)
        baseline = run(scene)
        changed = {sym: [dict(r, updated_at="2099-01-01T00:00:00Z",
                              volume_unit="unknown") for r in rows]
                   for sym, rows in scene["extract"]["rows"].items()}
        rebind(scene, changed)
        result = run(scene)
        assert result["deterministic_sha256"] != baseline["deterministic_sha256"], \
            "altered retained evidence produced an identical deterministic hash"
        assert result["deterministic"]["verdicts"]["capability"] != chk.CAPABILITY_PASS
        i3 = [c for c in result["deterministic"]["checks"]
              if c["id"] == "I3" and c["symbol"] == "sh600011"][0]
        assert i3["status"] == chk.INCONCLUSIVE and "volume unit" in i3["detail"], i3


@case("J-B5 an unpinned calendar or dependency is refused")
def _():
    with tempfile.TemporaryDirectory() as d:
        scene = scenario(d)
        det = run(scene, calendar_path=REPO_CALENDAR_COPY)["deterministic"]
        ev4 = [c for c in det["checks"] if c["id"] == "EV4"][0]
        assert ev4["status"] == "FAIL" and "calendar_sha256" in str(ev4["detail"]), ev4

    with tempfile.TemporaryDirectory() as d:
        scene = scenario(d)
        scene["manifest"]["environment"]["hk_js_decode_sha256"] = "0" * 64
        det = run(scene)["deterministic"]
        ev4 = [c for c in det["checks"] if c["id"] == "EV4"][0]
        assert ev4["status"] == "FAIL", ev4
        assert det["verdicts"]["capability"] == chk.CAPABILITY_FAIL


@case("J-B5 the frozen threshold contract is verified against the applied checks")
def _():
    with tempfile.TemporaryDirectory() as d:
        scene = scenario(d)
        rules = dict(scene["extract"]["rules"])
        rules["thresholds"] = dict(rules["thresholds"], volume_ratio_stock=1.0)
        scene["extract"] = dict(scene["extract"], rules=rules)
        scene["extract"]["content_sha256"] = cap.canonical_sha256(
            {"rules": rules, "rows": scene["extract"]["rows"]})
        scene["manifest"]["reference_extract_sha256"] = scene["extract"]["content_sha256"]
        det = run(scene)["deterministic"]
        ev5 = [c for c in det["checks"] if c["id"] == "EV5"][0]
        assert ev5["status"] == "FAIL" and "thresholds" in str(ev5["detail"]), ev5
        assert det["verdicts"]["capability"] == chk.CAPABILITY_FAIL


@case("J-B5 corrupted retained evidence is caught on replay as well as on first check")
def _():
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        scene = scenario(d)
        first = run(scene)
        (d / "checks.json").write_text(json.dumps(first, default=str), encoding="utf-8")
        raw = d / "raw" / PLANNED[0]["filename"]
        raw.write_bytes(raw.read_bytes() + b" ")
        global FAKE_REPLAY_DATES
        FAKE_REPLAY_DATES = {job: [r["date"] for r in rows]
                             for job, rows in scene["live"].items()}
        result = chk.replay(d, replay_fn=fake_replay, routine=FAKE_ROUTINE,
                            routine_sha256=FAKE_ROUTINE_SHA,
                            racer_factory=scene["racer"])
        assert result["matches_stored"] is False
        ev1 = [c for c in result["deterministic"]["checks"] if c["id"] == "EV1"][0]
        assert ev1["status"] == "FAIL", ev1
        assert result["deterministic"]["verdicts"]["capability"] != chk.CAPABILITY_PASS


@case("J-B5 capture and checks must agree on what a retained body was")
def _():
    with tempfile.TemporaryDirectory() as d:
        scene = scenario(d, specs={1: {"outcome": "ok", "payload_state": "decoded",
                                       "body": HTML}})
        det = run(scene)["deterministic"]
        ev6 = [c for c in det["checks"] if c["id"] == "EV6"][0]
        assert ev6["status"] == "FAIL" and "classify as" in ev6["detail"], ev6
        assert det["verdicts"]["capability"] != chk.CAPABILITY_PASS


@case("J-hardening the guard refuses the configured loopback proxy and real HTTP")
def _():
    fake_env = lambda: {"http": "http://127.0.0.1:7892", "https": "http://127.0.0.1:7892"}
    assert cap.proxy_endpoints(fake_env) == {("127.0.0.1", 7892)}
    with cap.no_remote_connections("offline test", getproxies=fake_env,
                                   requests_module=requests):
        try:
            socket.create_connection(("127.0.0.1", 7892), timeout=1)
        except AssertionError as exc:
            assert "configured proxy" in str(exc), str(exc)
        else:
            raise AssertionError("a loopback proxy tunnel was permitted")
        try:
            requests.Session().request("GET", "https://finance.sina.com.cn/")
        except AssertionError as exc:
            assert "genuine HTTP" in str(exc), str(exc)
        else:
            raise AssertionError("a genuine HTTP request was permitted")
        # The JS engine's own loopback self-pipe still works.
        import py_mini_racer

        assert py_mini_racer.MiniRacer().eval("1+1") == 2
    # The suite-level guard entered at import is still in force after the inner one
    # exits: nesting restores the previous state, which is itself refusing.
    try:
        requests.Session().request("GET", "https://finance.sina.com.cn/")
    except AssertionError as exc:
        assert "M2b test suite" in str(exc), str(exc)
    else:
        raise AssertionError("the suite-level offline guard was lost")


@case("J-hardening the installed adapter replay inherits the decoder's JS limits")
def _():
    from akshare.stock import stock_zh_a_sina

    seen = {}

    def probe(symbol):
        import pandas as pd

        racer = stock_zh_a_sina.py_mini_racer.MiniRacer()
        seen["class"] = type(racer).__name__
        seen["value"] = racer.eval("1+1")
        return pd.DataFrame({"date": ["2024-08-13"]})

    url = "https://example.invalid/probe"
    stock_zh_a_sina._m2b_probe = probe
    try:
        chk.adapter_replay({url: (b'var a="K2x";', "utf-8")},
                           [("probe", "stock", "_m2b_probe", ("x",))])
    finally:
        del stock_zh_a_sina._m2b_probe
    assert seen["class"] == "BoundedRacer", seen
    assert seen["value"] == 2
    assert stock_zh_a_sina.py_mini_racer.__name__ == "py_mini_racer"


# ============================================ K: closure round 3 - R1, R2, R3, R4
import threading                                       # noqa: E402
from unittest.mock import patch as _patch              # noqa: E402


def _tree(root):
    """Every file under `root` with its hash: the whole tree, not only the manifest."""
    root = Path(root)
    return {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(root.rglob("*")) if p.is_file()}


def _join_workers(before, timeout=5.0):
    for worker in set(threading.enumerate()) - before:
        if worker.name.startswith("m2b-"):
            worker.join(timeout)
            assert not worker.is_alive(), "worker %s is still alive" % worker.name


def _paused_worker_capture(root, scene, *, target, attr, override=None):
    """Capture with a REAL supervised worker paused inside `target.attr` after the
    response arrived. While it waits the run budget is spent, the supervisor abandons
    it, seals the tree and returns the aborted manifest. The worker is then released.

    Returns (run, manifest, tree_at_seal, manifest_bytes_at_seal, workers_before).
    """
    clock = Clock()
    run_obj = cap.SmokeRun("20260907T010000Z", out_root=Path(root) / "capture",
                           evidence_root=Path(root) / "evidence", clock=clock,
                           sleeper=clock.advance)
    waiting, release = threading.Event(), threading.Event()
    original = getattr(target, attr)

    def gated(*args, **kwargs):
        if not waiting.is_set():
            waiting.set()
            clock.advance(10_000.0)          # the run budget is spent while we wait
            if not release.wait(5):
                raise RuntimeError("the test failed to release the paused worker")
        return original(*args, **kwargs)

    workers_before = set(threading.enumerate())
    with synthetic_preflight(scene["extract"]), _patch.object(target, attr, gated):
        try:
            manifest = run_obj.capture(
                session=FakeSession(wire_handler(scene, override=override)),
                requests_module=requests, supervise_jobs=True, poll_sec=0.01,
                routine=FAKE_ROUTINE, routine_sha256=FAKE_ROUTINE_SHA,
                racer_factory=scene["racer"])
            assert waiting.is_set(), "the worker never reached the pause point"
            assert run_obj.cancelled is True
            assert manifest["run_status"] == "aborted", manifest["run_status"]
            tree = _tree(run_obj.out_root)
            stored = (run_obj.out_root / "capture_manifest.json").read_bytes()
        finally:
            release.set()
        _join_workers(workers_before)
    return run_obj, manifest, tree, stored, workers_before


@case("K-R1 a worker paused at the real raw publication cannot write after the seal")
def _():
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        scene = scenario(d / "scene")
        run_obj, manifest, tree, stored, _w = _paused_worker_capture(
            d, scene, target=cap.EvidenceStore, attr="publish")
        raw = run_obj.out_root / "raw" / PLANNED[0]["filename"]
        assert not raw.exists(), "the late worker published a raw body after the seal"
        assert _tree(run_obj.out_root) == tree, "the evidence tree changed after the seal"
        assert (run_obj.out_root / "capture_manifest.json").read_bytes() == stored
        assert run_obj.store.refused and run_obj.store.refused[0]["relative"].endswith(
            PLANNED[0]["filename"]), run_obj.store.refused
        # The attempt happened and is evidenced; the request is honestly ABORTED and
        # abandoned, not skipped, so the attempt evidence reconciles.
        first = manifest["requests"][0]
        assert first["outcome"] == "aborted" and first.get("abandoned") is True, first
        assert manifest["attempts"][0]["request_index"] == 1
        assert manifest["attempts"][0]["status"] == 200
        # The staged bytes were discarded, never moved into the tree.
        pending = run_obj.store.discard_pending()
        assert pending["leftover_staged"] == [], pending
        # The run budget is spent, so this is the later offline replay's own budget.
        det = check_captured(run_obj, manifest, scene,
                             deadline=cap.Deadline(cap.REPLAY_BUDGET_SEC, clock=Clock(),
                                                   label="replay"))["deterministic"]
        t3 = [c for c in det["checks"] if c["id"] == "T3"][0]
        assert t3["status"] == "PASS", t3["detail"]
        assert det["verdicts"]["capability"] != chk.CAPABILITY_PASS


@case("K-R1 a failed-response body paused at publication is refused the same way")
def _():
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        scene = scenario(d / "scene")
        run_obj, manifest, tree, stored, _w = _paused_worker_capture(
            d, scene, target=cap.EvidenceStore, attr="publish",
            override={1: lambda item: FakeHttpResponse(404, b"not found", item["url"])})
        failed = run_obj.out_root / "raw" / ("failed_%s" % PLANNED[0]["filename"])
        assert not failed.exists(), "a failed body was published after the seal"
        assert _tree(run_obj.out_root) == tree
        assert (run_obj.out_root / "capture_manifest.json").read_bytes() == stored
        assert manifest["requests"][0]["outcome"] == "aborted"
        assert manifest["attempts"][0]["status"] == 404


@case("K-R1 a worker released after the seal never reaches the wire")
def _():
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        scene = scenario(d / "scene")
        seen = []
        clock = Clock()
        run_obj = cap.SmokeRun("20260907T010000Z", out_root=d / "capture",
                               evidence_root=d / "evidence", clock=clock,
                               sleeper=clock.advance)
        waiting, release = threading.Event(), threading.Event()
        original = cap.TimedTransport.__call__

        def gated(self, url, **kwargs):
            if not waiting.is_set():
                waiting.set()
                clock.advance(10_000.0)
                if not release.wait(5):
                    raise RuntimeError("release failed")
            return original(self, url, **kwargs)

        workers_before = set(threading.enumerate())
        with synthetic_preflight(scene["extract"]), \
                _patch.object(cap.TimedTransport, "__call__", gated):
            try:
                manifest = run_obj.capture(
                    session=FakeSession(wire_handler(scene, seen=seen)),
                    requests_module=requests, supervise_jobs=True, poll_sec=0.01,
                    routine=FAKE_ROUTINE, routine_sha256=FAKE_ROUTINE_SHA,
                    racer_factory=scene["racer"])
                tree = _tree(run_obj.out_root)
            finally:
                release.set()
            _join_workers(workers_before)
        assert seen == [], "a request reached the wire after the seal: %r" % seen
        assert manifest["attempts"] == [], manifest["attempts"]
        assert all(r["outcome"] == "skipped" for r in manifest["requests"])
        assert _tree(run_obj.out_root) == tree


@case("K-R2 a finalization that returns after its budget is reported incomplete")
def _():
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        scene = scenario(d / "scene")
        clock = Clock()
        run_obj = cap.SmokeRun("20260907T010000Z", out_root=d / "capture",
                               evidence_root=d / "evidence", clock=clock,
                               sleeper=clock.advance)
        original = cap.SmokeRun.cleanup

        def slow_cleanup(self, **kwargs):
            clock.advance(cap.FINALIZE_BUDGET_SEC + 1.0)
            return original(self, **kwargs)

        global FAKE_REPLAY_DATES
        FAKE_REPLAY_DATES = {job: [r["date"] for r in rows]
                             for job, rows in scene["live"].items()}
        with synthetic_preflight(scene["extract"]), \
                _patch.object(cap.SmokeRun, "cleanup", slow_cleanup):
            record = run_obj.run_pipeline(
                session=FakeSession(wire_handler(scene)), requests_module=requests,
                supervise_jobs=False, routine=FAKE_ROUTINE,
                routine_sha256=FAKE_ROUTINE_SHA, racer_factory=scene["racer"],
                replay_fn=fake_replay, plan_text="synthetic plan")
        assert record["phase"] == "incomplete_finalization", record["phase"]
        assert record["finalize"]["status"] == "overrun", record["finalize"]
        assert record["finalize"]["remaining_sec"] < 0
        assert record["capability"] == chk.CAPABILITY_PASS   # the checks did pass ...
        assert cap.exit_code_for(record) == 1                 # ... but the run is not done
        assert (run_obj.evidence_dir / "REPORT.md").exists()
        assert not run_obj.out_root.exists()


@case("K-R2 a retention step that blocks is abandoned, and the evidence stays intact")
def _():
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        scene = scenario(d / "scene")
        clock = Clock()
        run_obj = cap.SmokeRun("20260907T010000Z", out_root=d / "capture",
                               evidence_root=d / "evidence", clock=clock,
                               sleeper=clock.advance)
        entered, release = threading.Event(), threading.Event()
        original_rename = os.rename

        def blocked_rename(src, dst, *args, **kwargs):
            if Path(dst) == run_obj.evidence_dir:
                entered.set()
                clock.advance(cap.FINALIZE_BUDGET_SEC + 1.0)
                if not release.wait(5):
                    raise RuntimeError("release failed")
            return original_rename(src, dst, *args, **kwargs)

        global FAKE_REPLAY_DATES
        FAKE_REPLAY_DATES = {job: [r["date"] for r in rows]
                             for job, rows in scene["live"].items()}
        workers_before = set(threading.enumerate())
        with synthetic_preflight(scene["extract"]), _patch.object(os, "rename", blocked_rename):
            try:
                record = run_obj.run_pipeline(
                    session=FakeSession(wire_handler(scene)), requests_module=requests,
                    supervise_jobs=False, routine=FAKE_ROUTINE,
                    routine_sha256=FAKE_ROUTINE_SHA, racer_factory=scene["racer"],
                    replay_fn=fake_replay, plan_text="synthetic plan")
                assert entered.is_set()
                assert record["phase"] == "incomplete_finalization", record["phase"]
                assert record["finalize"]["status"] == "abandoned", record["finalize"]
                assert record["finalize"]["step"] == "retain"
                assert record["finalize"]["partial"] is True
                assert cap.exit_code_for(record) == 1
                locations = record["finalize"]["evidence_location"]
                assert str(run_obj.out_root) in locations and str(run_obj.evidence_dir) in locations
                # The blocked step has not moved the tree yet; the report is already in it.
                assert run_obj.out_root.exists() and not run_obj.evidence_dir.exists()
                assert (run_obj.out_root / "REPORT.md").exists()
                assert (run_obj.out_root / "checks.json").exists()
                frozen = _tree(run_obj.out_root)
            finally:
                release.set()
            _join_workers(workers_before)
        # The abandoned step completed its one blocked operation and nothing else: the
        # tree is at exactly ONE location, byte-identical to what was reported.
        assert run_obj.evidence_dir.exists() != run_obj.out_root.exists()
        where = run_obj.evidence_dir if run_obj.evidence_dir.exists() else run_obj.out_root
        assert _tree(where) == frozen, "the retained tree changed after abandonment"
        assert not (where / "finalization.json").exists()


@case("K-R2 a worker holding the evidence lock past the seal timeout yields an UNSEALED run")
def _():
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        scene = scenario(d / "scene")
        clock = Clock()
        run_obj = cap.SmokeRun("20260907T010000Z", out_root=d / "capture",
                               evidence_root=d / "evidence", clock=clock,
                               sleeper=clock.advance)
        waiting, release = threading.Event(), threading.Event()
        original_replace = os.replace
        seen = []

        def blocked_replace(src, dst, *args, **kwargs):
            # Inside publish(), UNDER the evidence lock, on the first raw body.
            if Path(dst).name == PLANNED[0]["filename"] and not waiting.is_set():
                waiting.set()
                clock.advance(10_000.0)
                if not release.wait(5):
                    raise RuntimeError("release failed")
            return original_replace(src, dst, *args, **kwargs)

        workers_before = set(threading.enumerate())
        with synthetic_preflight(scene["extract"]), _Restore(SEAL_TIMEOUT_SEC=0.2), \
                _patch.object(os, "replace", blocked_replace):
            try:
                record = run_obj.run_pipeline(
                    session=FakeSession(wire_handler(scene, seen=seen)),
                    requests_module=requests, supervise_jobs=True,
                    routine=FAKE_ROUTINE, routine_sha256=FAKE_ROUTINE_SHA,
                    racer_factory=scene["racer"], replay_fn=fake_replay)
                assert waiting.is_set()
                assert record["phase"] == "incomplete_finalization", record["phase"]
                assert record["finalize"]["status"] == "unsealed", record["finalize"]
                assert record["capability"] == chk.CAPABILITY_INCONCLUSIVE
                assert cap.exit_code_for(record) == 1
                assert run_obj.store.sealed and "FORCED" in run_obj.store.seal_reason
                # Nothing was written or retained by the owner.
                assert not (run_obj.out_root / "REPORT.md").exists()
                assert not (run_obj.out_root / "checks.json").exists()
                assert not run_obj.evidence_dir.exists()
            finally:
                release.set()
            _join_workers(workers_before)
        # The one publication that was already inside its critical section completed
        # as a UNIT (body + record + manifest), and no further request was issued.
        assert seen == [1], seen
        manifest = json.loads((run_obj.out_root / "capture_manifest.json")
                              .read_text(encoding="utf-8"))
        first = [r for r in manifest["requests"] if r["index"] == 1]
        assert first and first[0]["outcome"] == "ok", manifest["requests"]
        assert (run_obj.out_root / "raw" / PLANNED[0]["filename"]).exists()


@case("K-R3 five successes with an emptied attempt list can no longer validate")
def _():
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        scene = scenario(d / "scene")
        run_obj, manifest, _clock = capture_scene(d, scene, wire_handler(scene))
        manifest["attempts"] = []
        result = check_captured(run_obj, manifest, scene)
        t3 = [c for c in result["deterministic"]["checks"] if c["id"] == "T3"][0]
        assert t3["status"] == "FAIL" and "no attempt evidence" in t3["detail"], t3
        assert result["deterministic"]["verdicts"]["capability"] == chk.CAPABILITY_FAIL
        # ... and on the retained-evidence replay path as well.
        (run_obj.out_root / "capture_manifest.json").write_text(
            json.dumps(manifest), encoding="utf-8")
        global FAKE_REPLAY_DATES
        FAKE_REPLAY_DATES = {job: [r["date"] for r in rows]
                             for job, rows in scene["live"].items()}
        replayed = chk.replay(run_obj.out_root, replay_fn=fake_replay,
                              routine=FAKE_ROUTINE, routine_sha256=FAKE_ROUTINE_SHA,
                              racer_factory=scene["racer"])
        t3 = [c for c in replayed["deterministic"]["checks"] if c["id"] == "T3"][0]
        assert t3["status"] == "FAIL", t3
        assert replayed["deterministic"]["verdicts"]["capability"] == chk.CAPABILITY_FAIL


@case("K-R3 truncated, duplicated, misbound and orphaned attempt records are rejected")
def _():
    def mutate(fn, expect):
        with tempfile.TemporaryDirectory() as d:
            scene = scenario(d, specs={5: {"outcome": "skipped"}} if expect == "skipped"
                             else None)
            fn(scene["manifest"])
            det = run(scene)["deterministic"]
            t3 = [c for c in det["checks"] if c["id"] == "T3"][0]
            assert t3["status"] == "FAIL" and expect in t3["detail"], (expect, t3["detail"])
            assert det["verdicts"]["capability"] == chk.CAPABILITY_FAIL

    def truncate(m):
        m["attempts"].pop()                       # request 5 loses its only attempt
    mutate(truncate, "transport counted")

    def duplicate(m):
        m["attempts"].append(dict(m["attempts"][0],
                                  started_at_monotonic=m["attempts"][-1]["started_at_monotonic"] + 2.0,
                                  finished_at_monotonic=m["attempts"][-1]["started_at_monotonic"] + 2.1))
        m["attempt_count_transport"] = len(m["attempts"])
    mutate(duplicate, "resume at position")

    def misbind(m):
        m["attempts"][2]["url"] = m["attempts"][0]["url"]
    mutate(misbind, "URL differs")

    def orphan(m):
        last = m["attempts"][-1]
        m["attempts"].append(dict(last, request_index=5, attempt_no=1,
                                  url=m["requests"][4]["requested_url"],
                                  started_at_monotonic=last["started_at_monotonic"] + 2.0,
                                  finished_at_monotonic=last["started_at_monotonic"] + 2.1))
        m["attempt_count_transport"] = len(m["attempts"])
    mutate(orphan, "skipped")

    def miscount(m):
        m["attempt_count_transport"] = len(m["attempts"]) + 1
    mutate(miscount, "transport counted")

    def unfinished(m):
        m["attempts"][1]["finished_at_monotonic"] = None
    mutate(unfinished, "no finish record")


@case("K-R3 retries are real attempts, persisted at the boundary, and reconcile")
def _():
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        scene = scenario(d / "scene")
        clock = Clock()
        run_obj = cap.SmokeRun("20260907T010000Z", out_root=d / "capture",
                               evidence_root=d / "evidence", clock=clock,
                               sleeper=clock.advance)
        calls = {"n": 0}
        on_disk = {}
        by_url = {item["url"]: item for item in PLANNED}

        def handler(url):
            item = by_url[url]
            if item["index"] == 1:
                calls["n"] += 1
                if calls["n"] == 2:
                    # Persisted at the attempt boundary: attempt 1 is on disk with its
                    # terminal outcome, and attempt 2 is on disk as IN FLIGHT.
                    on_disk.update(json.loads((run_obj.out_root / "capture_manifest.json")
                                              .read_text(encoding="utf-8")))
                if calls["n"] < 3:
                    return FakeHttpResponse(503, b"busy", url)
            return FakeHttpResponse(200, scene["bodies"][item["index"]], url)

        with synthetic_preflight(scene["extract"]):
            manifest = run_obj.capture(
                session=FakeSession(handler), requests_module=requests,
                supervise_jobs=False, routine=FAKE_ROUTINE,
                routine_sha256=FAKE_ROUTINE_SHA, racer_factory=scene["racer"])
        first = [a for a in manifest["attempts"] if a["request_index"] == 1]
        assert [a["attempt_no"] for a in first] == [1, 2, 3], first
        assert [a["transport_outcome"] for a in first] == ["retryable", "retryable", "ok"]
        assert [a["status"] for a in first] == [503, 503, 200]
        assert manifest["requests"][0]["attempt_count"] == 3
        assert len(manifest["attempts"]) == 7 and manifest["attempt_count_transport"] == 7
        stamps = [a["started_at_monotonic"] for a in manifest["attempts"]]
        assert all(b - a >= cap.MIN_INTERVAL for a, b in zip(stamps, stamps[1:])), stamps
        assert on_disk["attempts"][0]["status"] == 503
        assert on_disk["attempts"][0]["transport_outcome"] == "retryable"
        assert on_disk["attempts"][1]["finished_at_monotonic"] is None, on_disk["attempts"][1]
        det = check_captured(run_obj, manifest, scene)["deterministic"]
        t3 = [c for c in det["checks"] if c["id"] == "T3"][0]
        assert t3["status"] == "PASS", t3["detail"]
        assert t3["measured"]["retries"] == 2, t3["measured"]
        assert det["verdicts"]["capability"] == chk.CAPABILITY_PASS


@case("K-R3 an interrupted retry sequence leaves every attempt it made on disk")
def _():
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        scene = scenario(d / "scene")
        clock = Clock()
        run_obj = cap.SmokeRun("20260907T010000Z", out_root=d / "capture",
                               evidence_root=d / "evidence", clock=clock,
                               sleeper=clock.advance)
        calls = {"n": 0}

        def handler(url):
            calls["n"] += 1
            if calls["n"] == 2:
                clock.advance(10_000.0)       # the budget dies during the second attempt
            return FakeHttpResponse(503, b"busy", url)

        with synthetic_preflight(scene["extract"]):
            manifest = run_obj.capture(
                session=FakeSession(handler), requests_module=requests,
                supervise_jobs=False, routine=FAKE_ROUTINE,
                routine_sha256=FAKE_ROUTINE_SHA, racer_factory=scene["racer"])
        assert manifest["run_status"] == "aborted"
        attempts = manifest["attempts"]
        assert [a["request_index"] for a in attempts] == [1, 1, 1], attempts
        assert [a["transport_outcome"] for a in attempts] == ["retryable", "retryable", "stop"]
        assert attempts[2]["error"] == "DeadlineExceeded" and attempts[2]["status"] is None
        assert manifest["requests"][0]["outcome"] == "aborted"
        stored = json.loads((run_obj.out_root / "capture_manifest.json")
                            .read_text(encoding="utf-8"))
        assert stored["attempts"] == attempts
        det = check_captured(run_obj, manifest, scene,
                             deadline=cap.Deadline(cap.REPLAY_BUDGET_SEC, clock=Clock(),
                                                   label="replay"))["deterministic"]
        t3 = [c for c in det["checks"] if c["id"] == "T3"][0]
        assert t3["status"] == "PASS", t3["detail"]
        # The reviewed outcome table classifies a request cut off by the run deadline
        # as a FAILED job ("aborted" row), so the capability is FAIL - never PASS.
        assert det["job_results"]["sh600011"] == chk.JOB_FAILED, det["job_results"]
        assert det["verdicts"]["capability"] == chk.CAPABILITY_FAIL, det["verdicts"]


@case("K-R4 an explicit 404 on the BJ KLC history request is the documented finding")
def _():
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        scene = scenario(d / "scene")
        seen = []
        run_obj, manifest, _clock = capture_scene(
            d, scene, wire_handler(scene, seen=seen, override={
                4: lambda item: FakeHttpResponse(404, b"gone", item["url"])}))
        assert 5 not in seen, seen
        det = check_captured(run_obj, manifest, scene)["deterministic"]
        assert det["job_results"]["bj920000"] == chk.JOB_NOT_SERVED
        assert det["verdicts"]["capability"] == chk.CAPABILITY_PASS_BJ, det["verdicts"]
        c2 = [c for c in det["checks"] if c["id"] == "C2"][0]
        assert c2["measured"]["classification"] == "vendor_explicit_absence_at_path"
        assert c2["measured"]["decided_by"] == "klc"
        assert c2["measured"]["klc_request"]["status"] == 404


@case("K-R4 a 404 on the auxiliary share endpoint never becomes BJ history non-service")
def _():
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        scene = scenario(d / "scene")
        run_obj, manifest, _clock = capture_scene(
            d, scene, wire_handler(scene, override={
                5: lambda item: FakeHttpResponse(404, b"gone", item["url"])}))
        assert manifest["requests"][3]["payload_state"] == "decoded"
        assert manifest["requests"][4]["status"] == 404
        det = check_captured(run_obj, manifest, scene)["deterministic"]
        assert det["job_results"]["bj920000"] == chk.JOB_INCONCLUSIVE_AUXILIARY
        assert det["verdicts"]["per_job"]["bj920000"] == chk.INCONCLUSIVE, det["verdicts"]
        assert det["verdicts"]["capability"] == chk.CAPABILITY_INCONCLUSIVE, det["verdicts"]
        c2 = [c for c in det["checks"] if c["id"] == "C2"][0]
        assert c2["measured"]["classification"] == "pre_boundary_history_served", c2
        assert c2["measured"]["auxiliary_evidence"] == "absent"
        assert c2["measured"]["outstanding_share_request"]["status"] == 404
        ids = {c["id"] for c in det["checks"] if c["symbol"] == "bj920000"}
        for cid in ("JOBaux", "D1", "D2", "D3", "D4", "C2span", "I2"):
            assert cid in ids, (cid, sorted(ids))
        d5 = [c for c in det["checks"] if c["id"] == "D5" and c["symbol"] == "bj920000"][0]
        assert d5["status"] == chk.INCONCLUSIVE and "AUXILIARY" in d5["detail"], d5
        assert "vendor_explicit_absence_at_path" not in json.dumps(det["verdicts"])


@case("K-R4 invalid BJ history is still a FAIL when the auxiliary endpoint is absent")
def _():
    def broken(live):
        rows = live["bj920000"]
        target = next(r for r in rows if cap.RESEARCH_START <= r["date"] <= cap.RESEARCH_END)
        target["high"] = round(target["low"] - 1.0, 2)      # OHLC ordering broken
        return live

    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        scene = scenario(d / "scene", live_override=broken)
        run_obj, manifest, _clock = capture_scene(
            d, scene, wire_handler(scene, override={
                5: lambda item: FakeHttpResponse(404, b"gone", item["url"])}))
        det = check_captured(run_obj, manifest, scene)["deterministic"]
        d4 = [c for c in det["checks"] if c["id"] == "D4" and c["symbol"] == "bj920000"][0]
        assert d4["status"] == "FAIL", d4
        assert det["verdicts"]["per_job"]["bj920000"] == "FAIL", det["verdicts"]
        assert det["verdicts"]["capability"] == chk.CAPABILITY_FAIL, det["verdicts"]


# ===== K2: the pre-seal window, guarded owner writes, and cross-checked attempts =====
def _released_before_seal(root, scene, *, target, attr, override=None):
    """Capture with a worker paused inside `target.attr`, released AFTER the owner has
    written its abandonment records and BEFORE the seal - the window the reviewer used.

    The release happens inside `protected_fingerprints`, which capture calls between the
    last `close_unissued` and `store.seal`.
    """
    clock = Clock()
    run_obj = cap.SmokeRun("20260907T010000Z", out_root=Path(root) / "capture",
                           evidence_root=Path(root) / "evidence", clock=clock,
                           sleeper=clock.advance)
    waiting, release = threading.Event(), threading.Event()
    observed = {}
    original = getattr(target, attr)

    def gated(*args, **kwargs):
        if not waiting.is_set():
            waiting.set()
            clock.advance(10_000.0)
            if not release.wait(5):
                raise RuntimeError("the test failed to release the paused worker")
            store = getattr(args[0], "store", args[0])
            observed["refusing_at_resume"] = getattr(store, "refusing", None)
            observed["sealed_at_resume"] = getattr(store, "sealed", None)
        return original(*args, **kwargs)

    workers_before = set(threading.enumerate())
    with synthetic_preflight(scene["extract"]), _patch.object(target, attr, gated):
        def fingerprints_between_records_and_seal():
            release.set()
            _join_workers(workers_before)
            observed["records_before_seal"] = [
                (r["index"], r["outcome"]) for r in run_obj.requests_log]
            return {}

        with _Restore(protected_fingerprints=fingerprints_between_records_and_seal):
            manifest = run_obj.capture(
                session=FakeSession(wire_handler(scene, override=override)),
                requests_module=requests, supervise_jobs=True, poll_sec=0.01,
                routine=FAKE_ROUTINE, routine_sha256=FAKE_ROUTINE_SHA,
                racer_factory=scene["racer"])
        assert waiting.is_set(), "the worker never reached the pause point"
    return run_obj, manifest, observed


@case("K-R1 a worker released BEFORE the seal is already refused, and adds no record")
def _():
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        scene = scenario(d / "scene")
        run_obj, manifest, observed = _released_before_seal(
            d, scene, target=cap.EvidenceStore, attr="stage")
        # Refusal is set by the owner INSIDE the critical section that writes the
        # abandonment record, so it is already in force when the worker wakes - the
        # seal alone would have left this window open.
        assert observed["refusing_at_resume"], observed
        assert observed["sealed_at_resume"] is False, observed
        assert not (run_obj.out_root / "raw" / PLANNED[0]["filename"]).exists()
        indices = [r["index"] for r in manifest["requests"]]
        assert indices == sorted(set(indices)) and len(indices) == 5, manifest["requests"]
        first = manifest["requests"][0]
        assert first["outcome"] == "aborted" and first.get("abandoned") is True, first
        assert run_obj.store.published == [], run_obj.store.published
        det = check_captured(run_obj, manifest, scene,
                             deadline=cap.Deadline(cap.REPLAY_BUDGET_SEC, clock=Clock(),
                                                   label="replay"))["deterministic"]
        assert [c for c in det["checks"] if c["id"] == "EV0"][0]["status"] == "PASS"
        assert [c for c in det["checks"] if c["id"] == "T3"][0]["status"] == "PASS"
        assert det["verdicts"]["capability"] != chk.CAPABILITY_PASS


@case("K-R1 a worker released before the seal cannot add a second skip or classification")
def _():
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        scene = scenario(d / "scene")
        run_obj, manifest, observed = _released_before_seal(
            d, scene, target=cap.SmokeRun, attr="_classify",
            override={1: lambda item: FakeHttpResponse(200, HTML, item["url"])})
        assert observed["refusing_at_resume"], observed
        indices = [r["index"] for r in manifest["requests"]]
        assert indices == sorted(set(indices)) and len(indices) == 5, manifest["requests"]
        second = [r for r in manifest["requests"] if r["index"] == 2]
        assert len(second) == 1 and second[0]["outcome"] == "skipped"
        assert second[0]["skip_scope"] == out.SKIP_RUN_GLOBAL, second[0]
        # The body was published with its record BEFORE the pause, so it is bound.
        first = [r for r in manifest["requests"] if r["index"] == 1][0]
        assert first["outcome"] == "ok" and first["raw_file"] == PLANNED[0]["filename"]
        assert (run_obj.out_root / "raw" / PLANNED[0]["filename"]).exists()


@case("K-R1 a late call refused before the wire is evidenced as refused, not as a gap")
def _():
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        scene = scenario(d / "scene")
        run_obj, manifest, observed = _released_before_seal(
            d, scene, target=cap.TimedTransport, attr="__call__")
        assert observed["refusing_at_resume"], observed
        indices = [r["index"] for r in manifest["requests"]]
        assert indices == sorted(set(indices)) and len(indices) == 5, manifest["requests"]
        assert run_obj.store.published == [], run_obj.store.published
        assert not any((run_obj.out_root / "raw").iterdir())
        # The unchanged M2a transport counts the RunAborted it received, so the retained
        # attempt records must show that one refused call rather than nothing at all.
        assert len(manifest["attempts"]) == 1, manifest["attempts"]
        refused = manifest["attempts"][0]
        assert refused["refused_before_wire"] is True and refused["error"] == "RunAborted"
        assert refused["transport_outcome"] == "stop", refused
        assert manifest["attempt_count_transport"] == 1
        det = check_captured(run_obj, manifest, scene,
                             deadline=cap.Deadline(cap.REPLAY_BUDGET_SEC, clock=Clock(),
                                                   label="replay"))["deterministic"]
        t3 = [c for c in det["checks"] if c["id"] == "T3"][0]
        assert t3["status"] == "PASS", t3["detail"]
        # Nothing was collected, so every job fails on the pre-existing "a request never
        # issued is no free pass" rule; the refused call changes no verdict, it only
        # keeps the attempt evidence consistent with the transport's own count.
        assert det["verdicts"]["capability"] == chk.CAPABILITY_FAIL, det["verdicts"]


@case("K-R1 a publication whose record is refused leaves no orphan body in the tree")
def _():
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        scene = scenario(d / "scene")
        run_obj, _manifest, _clock = capture_scene(d, scene, wire_handler(scene))
        store = run_obj.store
        store.sealed, store.seal_reason = False, None      # reopen for the probe only
        staged = store.stage("probe.bin", b"body")
        try:
            store.publish("raw/probe.bin", staged,
                          lambda: (_ for _ in ()).throw(cap.SmokeError("record refused")))
        except cap.SmokeError:
            pass
        else:
            raise AssertionError("the failing record half was not propagated")
        assert not (run_obj.out_root / "raw" / "probe.bin").exists(), \
            "a body was published although its record failed"
        assert "raw/probe.bin" not in store.published, store.published
        assert staged.exists(), "the staged bytes were not returned to the staging area"


@case("K-R1 duplicate request records are rejected by the checker, not collapsed")
def _():
    with tempfile.TemporaryDirectory() as d:
        scene = scenario(d)
        first = dict(scene["manifest"]["requests"][0])
        scene["manifest"]["requests"].append(
            dict(first, outcome="aborted", abandoned=True, raw_file=None))
        det = run(scene)["deterministic"]
        ev0 = [c for c in det["checks"] if c["id"] == "EV0"][0]
        assert ev0["status"] == "FAIL" and "duplicate request records" in ev0["detail"], ev0
        assert det["verdicts"]["capability"] == chk.CAPABILITY_FAIL


@case("K-R2 an abandoned owner write lands at most its one blocked operation")
def _():
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        scene = scenario(d / "scene")
        clock = Clock()
        run_obj = cap.SmokeRun("20260907T010000Z", out_root=d / "capture",
                               evidence_root=d / "evidence", clock=clock,
                               sleeper=clock.advance)
        entered, release = threading.Event(), threading.Event()
        original_replace = os.replace

        def blocked_replace(src, dst, *args, **kwargs):
            if Path(dst).name == "checks.json" and not entered.is_set():
                entered.set()
                clock.advance(cap.FINALIZE_BUDGET_SEC + 1.0)
                if not release.wait(5):
                    raise RuntimeError("release failed")
            return original_replace(src, dst, *args, **kwargs)

        global FAKE_REPLAY_DATES
        FAKE_REPLAY_DATES = {job: [r["date"] for r in rows]
                             for job, rows in scene["live"].items()}
        workers_before = set(threading.enumerate())
        with synthetic_preflight(scene["extract"]), \
                _patch.object(os, "replace", blocked_replace):
            try:
                record = run_obj.run_pipeline(
                    session=FakeSession(wire_handler(scene)), requests_module=requests,
                    supervise_jobs=False, routine=FAKE_ROUTINE,
                    routine_sha256=FAKE_ROUTINE_SHA, racer_factory=scene["racer"],
                    replay_fn=fake_replay, plan_text="synthetic plan")
                assert entered.is_set()
                assert record["finalize"]["status"] == "abandoned", record["finalize"]
                assert record["finalize"]["step"] == "checks", record["finalize"]
                assert cap.exit_code_for(record) == 1
            finally:
                release.set()
            _join_workers(workers_before)
        # The steps AFTER the abandoned one never ran: no report, no retention, and the
        # staging area is not removed by the worker whose token was revoked.
        assert not (run_obj.out_root / "REPORT.md").exists()
        assert not run_obj.evidence_dir.exists()
        assert run_obj.out_root.exists()


@case("K-R2 a middle step that returns late is an overrun naming the step that did not run")
def _():
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        scene = scenario(d / "scene")
        clock = Clock()
        run_obj = cap.SmokeRun("20260907T010000Z", out_root=d / "capture",
                               evidence_root=d / "evidence", clock=clock,
                               sleeper=clock.advance)
        original_write = cap.EvidenceStore.owner_write

        def slow_write(self, relative, data, *, token=None):
            if relative == "REPORT.md":
                clock.advance(cap.FINALIZE_BUDGET_SEC + 1.0)
            return original_write(self, relative, data, token=token)

        global FAKE_REPLAY_DATES
        FAKE_REPLAY_DATES = {job: [r["date"] for r in rows]
                             for job, rows in scene["live"].items()}
        with synthetic_preflight(scene["extract"]), \
                _patch.object(cap.EvidenceStore, "owner_write", slow_write):
            record = run_obj.run_pipeline(
                session=FakeSession(wire_handler(scene)), requests_module=requests,
                supervise_jobs=False, routine=FAKE_ROUTINE,
                routine_sha256=FAKE_ROUTINE_SHA, racer_factory=scene["racer"],
                replay_fn=fake_replay, plan_text="synthetic plan")
        assert record["finalize"]["status"] == "overrun", record["finalize"]
        assert record["finalize"]["step"] == "retain", record["finalize"]
        assert "report" in record["finalize"]["steps_done"], record["finalize"]
        assert "abandoned" not in record["finalize"]["note"], record["finalize"]["note"]
        assert cap.exit_code_for(record) == 1
        assert run_obj.out_root.exists() and not run_obj.evidence_dir.exists()


@case("K-R2 retention that cannot be one rename fails with the tree intact")
def _():
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        scene = scenario(d / "scene")
        clock = Clock()
        run_obj = cap.SmokeRun("20260907T010000Z", out_root=d / "capture",
                               evidence_root=d / "evidence", clock=clock,
                               sleeper=clock.advance)

        def cross_device(self, source, destination, *, token=None):
            raise OSError(18, "Invalid cross-device link")

        global FAKE_REPLAY_DATES
        FAKE_REPLAY_DATES = {job: [r["date"] for r in rows]
                             for job, rows in scene["live"].items()}
        with synthetic_preflight(scene["extract"]), \
                _patch.object(cap.EvidenceStore, "owner_rename", cross_device):
            record = run_obj.run_pipeline(
                session=FakeSession(wire_handler(scene)), requests_module=requests,
                supervise_jobs=False, routine=FAKE_ROUTINE,
                routine_sha256=FAKE_ROUTINE_SHA, racer_factory=scene["racer"],
                replay_fn=fake_replay)
        assert record["finalize"]["status"] == "failed", record["finalize"]
        assert "one rename" in record["finalize"]["error"], record["finalize"]["error"]
        assert cap.exit_code_for(record) == 1
        assert run_obj.out_root.exists() and not run_obj.evidence_dir.exists()
        assert (run_obj.out_root / "raw" / PLANNED[0]["filename"]).exists()


@case("K-R2 keep_raw=False drops the bodies, keeps their hashes and leaves no staging dir")
def _():
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        scene = scenario(d / "scene")
        clock = Clock()
        run_obj = cap.SmokeRun("20260907T010000Z", out_root=d / "capture",
                               evidence_root=d / "evidence", clock=clock,
                               sleeper=clock.advance)
        global FAKE_REPLAY_DATES
        FAKE_REPLAY_DATES = {job: [r["date"] for r in rows]
                             for job, rows in scene["live"].items()}
        with synthetic_preflight(scene["extract"]):
            record = run_obj.run_pipeline(
                session=FakeSession(wire_handler(scene)), requests_module=requests,
                supervise_jobs=False, routine=FAKE_ROUTINE,
                routine_sha256=FAKE_ROUTINE_SHA, racer_factory=scene["racer"],
                replay_fn=fake_replay, keep_raw=False)
        assert record["finalize"]["status"] == "complete", record["finalize"]
        assert record["cleanup"]["raw_retained"] is False
        assert not (run_obj.evidence_dir / "raw").exists()
        report = (run_obj.evidence_dir / "REPORT.md").read_text(encoding="utf-8")
        assert "raw/%s" % PLANNED[0]["filename"] in report, "the body hashes were lost"
        assert not run_obj.store.pending_root.exists(), "the staging directory survived"
        assert not run_obj.out_root.exists()


@case("K-R3 an attempt whose classification contradicts its status is rejected")
def _():
    for mutate, expect in (
            (lambda m: m["attempts"][0].update(transport_outcome="failed"), "imply"),
            (lambda m: m["requests"][0].update(attempt_positions=[3]), "attempt binding"),
            (lambda m: m["requests"][0].pop("attempt_count"), "no attempt binding"),
            (lambda m: m["requests"][0].pop("attempt_positions"), "no attempt binding"),
    ):
        with tempfile.TemporaryDirectory() as d:
            scene = scenario(d)
            mutate(scene["manifest"])
            det = run(scene)["deterministic"]
            t3 = [c for c in det["checks"] if c["id"] == "T3"][0]
            assert t3["status"] == "FAIL" and expect in t3["detail"], (expect, t3["detail"])
            assert det["verdicts"]["capability"] == chk.CAPABILITY_FAIL


@case("K-R3 a failed request's terminal fields must match its final attempt")
def _():
    for mutate, expect in (
            (lambda m: m["requests"][3].update(transport_outcome="ok"),
             "records transport_outcome"),
            (lambda m: m["requests"][3].update(retryable=True), "records retryable"),
            (lambda m: m["requests"][3].update(failure_kind="tls"), "records failure_kind"),
    ):
        with tempfile.TemporaryDirectory() as d:
            scene = scenario(d, specs={4: {"outcome": "failed", "status": 404},
                                       5: {"outcome": "skipped"}})
            mutate(scene["manifest"])
            det = run(scene)["deterministic"]
            t3 = [c for c in det["checks"] if c["id"] == "T3"][0]
            assert t3["status"] == "FAIL" and expect in t3["detail"], (expect, t3["detail"])


@case("K-R3 an in-flight tail attempt must be genuinely in flight and uncounted")
def _():
    def probe(mutate):
        with tempfile.TemporaryDirectory() as d:
            scene = scenario(d)
            m = scene["manifest"]
            m["run_status"] = "aborted"
            m["abort_reason"] = "synthetic deadline"
            m["requests"][4].update(outcome="aborted", status=None, abandoned=True)
            m["attempts"][-1].update(finished_at_monotonic=None, elapsed_sec=None)
            mutate(m)
            det = run(scene)["deterministic"]
            return [c for c in det["checks"] if c["id"] == "T3"][0]

    # Genuine in-flight shape: no result, and the transport has not counted it yet.
    t3 = probe(lambda m: (m["attempts"][-1].update(status=None, error=None,
                                                   transport_outcome=None),
                          m.update(attempt_count_transport=len(m["attempts"]) - 1)))
    assert t3["status"] == "PASS", t3["detail"]
    # A "finished" result on an unfinished attempt is rejected.
    t3 = probe(lambda m: m.update(attempt_count_transport=len(m["attempts"]) - 1))
    assert t3["status"] == "FAIL" and "carries a result" in t3["detail"], t3["detail"]
    # An unfinished tail the transport already counted is rejected.
    t3 = probe(lambda m: (m["attempts"][-1].update(status=None, error=None,
                                                   transport_outcome=None),
                          m.update(attempt_count_transport=len(m["attempts"]))))
    assert t3["status"] == "FAIL" and "transport counted" in t3["detail"], t3["detail"]


@case("K-R4 a vendor stop on the auxiliary request fails the job, never inconclusive")
def _():
    for status in (403, 429):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            scene = scenario(d / "scene")
            run_obj, manifest, _clock = capture_scene(
                d, scene, wire_handler(scene, override={
                    5: lambda item, code=status: FakeHttpResponse(code, b"", item["url"])}))
            assert manifest["requests"][3]["payload_state"] == "decoded"
            aux = manifest["requests"][4]
            assert aux["outcome"] == "aborted" and aux["status"] == status, aux
            det = check_captured(run_obj, manifest, scene)["deterministic"]
            rows = det["outcomes"]["bj920000"]["requests"]
            assert rows[1]["transport_state"] == "vendor_stop", rows[1]
            assert det["job_results"]["bj920000"] == chk.JOB_FAILED, det["job_results"]
            assert det["verdicts"]["capability"] == chk.CAPABILITY_FAIL, det["verdicts"]


@case("K-R4 an auxiliary request the run abort never issued is inconclusive, not failed")
def _():
    with tempfile.TemporaryDirectory() as d:
        scene = scenario(d, specs={5: {"outcome": "skipped",
                                       "skip_scope": out.SKIP_RUN_GLOBAL}},
                         run_status="aborted", abort_reason="synthetic run abort")
        det = run(scene)["deterministic"]
        assert det["job_results"]["bj920000"] == chk.JOB_INCONCLUSIVE_AUXILIARY
        assert "run aborted first" in det["outcomes"]["bj920000"]["aggregation"]
        assert det["verdicts"]["per_job"]["bj920000"] == chk.INCONCLUSIVE
        assert det["verdicts"]["capability"] == chk.CAPABILITY_INCONCLUSIVE


@case("K-R4 an unusable auxiliary 200 body fails the job on its own required checks")
def _():
    for body, state in ((b"", "empty"), (HTML, "markup")):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            scene = scenario(d / "scene")
            run_obj, manifest, _clock = capture_scene(
                d, scene, wire_handler(scene, override={
                    5: lambda item, b=body: FakeHttpResponse(200, b, item["url"])}))
            assert manifest["requests"][4]["payload_state"] == state
            det = check_captured(run_obj, manifest, scene)["deterministic"]
            assert det["job_results"]["bj920000"] == chk.JOB_INCONCLUSIVE_AUXILIARY
            # T2 on the auxiliary body is a required check under this job's symbol, so
            # the job is FAIL - fail-closed, and never the BJ-qualified PASS.
            assert det["verdicts"]["per_job"]["bj920000"] == "FAIL", det["verdicts"]
            assert det["verdicts"]["capability"] == chk.CAPABILITY_FAIL



# ============ L: D1/D2 closure, on the hash-pinned real bodies from run 20260908T021722Z
# The two retained bodies are the ONLY real vendor samples this project has. They are
# referenced by SHA-256 so a substituted file fails the test rather than silently passing,
# and they are never modified: every negative case below is synthesised in memory.

REAL_EVIDENCE = HERE / "evidence_20260908T021722Z" / "raw"
REAL_BODIES = {
    "sh600011": ("01_sh600011_klc_kl.js.bin",
                 "adc5a39131ba32df3bdc53cbc47bcc842f9ed2c31c8e60cfe8173f2d387a2d02",
                 73353, "O", 5935),
    "sh000300": ("03_sh000300_klc_kl.js.bin",
                 "ef2180be45a1c1bb33f99772a55b410eb3923524d9b8fe268d549584a6e28647",
                 100465, "D", 5987),
}


def real_body(job):
    """The retained body, refused unless its SHA-256 still matches the pinned digest."""
    name, digest, size, _branch, _rows = REAL_BODIES[job]
    path = REAL_EVIDENCE / name
    if not path.exists():
        return None
    raw = path.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == digest, "retained body %s was modified" % name
    assert len(raw) == size, "retained body %s changed size" % name
    return raw


@case("L-D1 both retained real bodies now extract, and the trailer is recorded")
def _():
    for job, (_n, _d, _s, branch, rows) in REAL_BODIES.items():
        raw = real_body(job)
        if raw is None:
            raise AssertionError("retained real body for %s is missing" % job)
        text = dec.bytes_to_text(raw, None)
        name, payload, trailer = dec.extract_payload(text, with_trailer=True)
        assert name.lower().endswith(job), (job, name)
        assert payload == text.split("=")[1].split(";")[0].replace('"', ""), job
        assert trailer["comment_count"] == 1, (job, trailer)
        assert 200 < trailer["trailer_chars"] < 400, (job, trailer)
        code, observed = dec.header_branch(payload)
        assert observed == branch, (job, observed, branch)


@case("L-D1 the pinned routine decodes both retained bodies through the public decoder")
def _():
    from akshare.stock.cons import hk_js_decode

    for job, (_n, _d, _s, branch, rows) in REAL_BODIES.items():
        raw = real_body(job)
        if raw is None:
            raise AssertionError("retained real body for %s is missing" % job)
        out_rows = dec.decode_klc(raw, None, routine=hk_js_decode)
        assert out_rows["branch"] == branch, (job, out_rows["branch"])
        assert out_rows["row_count"] == rows, (job, out_rows["row_count"], rows)
        assert out_rows["trailer"]["comment_count"] == 1, job
        dates = [r["date"] for r in out_rows["rows"]]
        assert dates == sorted(set(dates)), job
        if job == "sh600011":
            assert "amount" in out_rows["observed_keys"], out_rows["observed_keys"]
        else:
            assert "amount" not in out_rows["observed_keys"], out_rows["observed_keys"]


@case("L-D1 an executable or malformed trailer is still refused")
def _():
    body = 'var klc_kl_sh600011="K2sh600011";'
    cases = [
        (body + ' var evil="x";', "unexpected trailing content"),
        (body + " alert(1);", "unexpected trailing content"),
        (body + " /* unterminated", "unterminated block comment"),
        (body + " // line comment", "unexpected trailing content"),
        (body + " /*ok*/ evil()", "unexpected trailing content"),
        (body + " /*a*/ }", "unexpected trailing content"),
        (body + " /*" + "x" * (dec.MAX_TRAILER_CHARS + 10) + "*/", "exceeds"),
        (body + (" /*a*/" * (dec.MAX_TRAILER_COMMENTS + 2)), "more than"),
    ]
    for text, fragment in cases:
        try:
            dec.extract_payload(text)
        except dec.DecodeError as exc:
            assert fragment in str(exc), (fragment, str(exc))
        else:
            raise AssertionError("accepted a bad trailer: %r" % text[-40:])


@case("L-D1 whitespace and several comments are accepted; markup and disagreement are not")
def _():
    payload = payload_for("sh600011")
    good = 'var klc_kl_sh600011="%s";\n\n/* a */\n  /* b */\n' % payload
    name, got, trailer = dec.extract_payload(good, with_trailer=True)
    assert got == payload and trailer["comment_count"] == 2, trailer
    for bad in (HTML.decode(), "   ", "notvar x=1;", 'var a="%s"' % payload):
        try:
            dec.extract_payload(bad)
        except dec.DecodeError:
            continue
        raise AssertionError("accepted %r" % bad[:40])


@case("L-D1 the decoder still refuses a body whose two extractions disagree")
def _():
    # An unescaped `=` inside the quoted payload makes the adapter's positional
    # extraction stop early; the strict parse sees the whole string. Refuse.
    text = 'var klc_kl_sh600011="AA=BB";'
    try:
        dec.extract_payload(text)
    except dec.DecodeError as exc:
        assert "disagree" in str(exc), str(exc)
    else:
        raise AssertionError("an extraction disagreement was accepted")


def f8_status(items):
    with tempfile.TemporaryDirectory() as d:
        checks, _ = preflight(d, process_lister=lambda: items)
        return by_id(checks)["F8"]


@case("L-D2 F8 fails closed on an unavailable, empty or malformed inventory")
def _():
    def boom():
        raise cap.InventoryUnavailable("synthetic: the query exited 1")

    check = f8_status([])
    assert check.status == "FAIL" and "empty" in check.detail, check.detail
    assert check.data.get("inventory_available") is False

    with tempfile.TemporaryDirectory() as d:
        checks, _ = preflight(d, process_lister=boom)
        check = by_id(checks)["F8"]
    assert check.status == "FAIL" and "unavailable" in check.detail, check.detail

    for broken in ("not a list", {"pid": 1}, None):
        with tempfile.TemporaryDirectory() as d:
            checks, _ = preflight(d, process_lister=lambda b=broken: b)
            assert by_id(checks)["F8"].status == "FAIL", broken


@case("L-D2 F8 recognises the API launch form run_stack.ps1 actually uses")
def _():
    check = f8_status(quiet_lister() + [
        {"pid": 424242, "name": "python.exe", "cmdline": REAL_API_COMMAND,
         "cmdline_available": True}])
    assert check.status == "FAIL", check.detail
    assert "appears to be running" in check.detail, check.detail
    assert any("app.main:app" in m["why"] for m in check.data["stack_matches"]), check.data


@case("L-D2 F8 recognises every supported worker, frontend and launcher form")
def _():
    forms = [
        ("python.exe", r"python.exe -X utf8 D:\p\backend\scripts\control_plane_loop.py --x 1"),
        ("python.exe", r"python.exe -X utf8 D:\p\backend\scripts\market_history_refresh_loop.py"),
        ("python.exe", r"python.exe -X utf8 D:\p\backend\scripts\codex_market_pulse.py --y"),
        ("python.exe", "python.exe -m uvicorn app.main:app --port 8000"),
        ("node.exe", r"node.exe D:\p\frontend\node_modules\vite\bin\vite.js --host 127.0.0.1"),
        ("powershell.exe", r"powershell.exe -File D:\p\scripts\run_stack.ps1 -Backend"),
        ("powershell.exe", r"powershell.exe -File D:\p\scripts\ensure_stack.ps1"),
    ]
    for image, cmd in forms:
        check = f8_status(quiet_lister() + [
            {"pid": 777, "name": image, "cmdline": cmd, "cmdline_available": True}])
        assert check.status == "FAIL", (cmd, check.detail)


@case("L-D2 a shell merely quoting those names is NOT a stack process")
def _():
    innocuous = [
        ("bash.exe", 'bash.exe -c "grep -n uvicorn app.main:app backend/scripts/x_loop.py"'),
        ("python.exe", 'python.exe -X utf8 -c "print(\'-m uvicorn app.main:app\')"'),
        ("powershell.exe", 'powershell.exe -NoProfile -Command "ls scripts/run_stack.ps1"'),
        ("code.exe", r"code.exe D:\p\backend\scripts\control_plane_loop.py"),
    ]
    for image, cmd in innocuous:
        check = f8_status(quiet_lister() + [
            {"pid": 888, "name": image, "cmdline": cmd, "cmdline_available": True}])
        assert check.status == "PASS", (cmd, check.detail)


@case("L-D2 an unreadable command line on a stack image is ambiguous, not stopped")
def _():
    check = f8_status(quiet_lister() + [
        {"pid": 999, "name": "python.exe", "cmdline": "", "cmdline_available": False}])
    assert check.status == "FAIL", check.detail
    assert "unproven" in check.detail, check.detail
    assert check.data["unreadable_relevant"][0]["pid"] == 999
    # An unreadable command line on an unrelated image is not evidence of anything.
    assert f8_status(quiet_lister()).status == "PASS"


@case("L-D2 the producer/decoder rejects failure, blank output and undecodable bytes")
def _():
    from types import SimpleNamespace

    def completed(code=0, out=b""):
        return SimpleNamespace(returncode=code, stdout=out, stderr=b"")

    for bad, fragment in (
            (completed(1, b'[{"ProcessId":1}]'), "exited 1"),
            (completed(0, b"   "), "no output"),
            (completed(0, b'\xff\xfe not utf8'), "did not decode"),
    ):
        try:
            cap._decode_inventory(bad)
        except cap.InventoryUnavailable as exc:
            assert fragment in str(exc), (fragment, str(exc))
        else:
            raise AssertionError("accepted %r" % (bad.stdout,))
    # lossy replacement is explicitly not the fallback
    try:
        cap._decode_inventory(completed(0, b'\xff'))
    except cap.InventoryUnavailable as exc:
        assert "errors='replace'" in str(exc), str(exc)


@case("L-D2 the inventory shape is validated: JSON, list, non-empty, complete records")
def _():
    bad = [
        ("not json", "not valid JSON"),
        ("[]", "empty"),
        ('"a string"', "not a list"),
        ('[{"Name":"x","CommandLine":"y"}]', "no ProcessId"),
        ('[{"ProcessId":1,"Name":"x"}]', "no CommandLine field"),
        ('[1,2]', "not an object"),
    ]
    for text, fragment in bad:
        try:
            cap._normalize_inventory(text)
        except cap.InventoryUnavailable as exc:
            assert fragment in str(exc), (fragment, str(exc))
        else:
            raise AssertionError("accepted %r" % text)
    ok = cap._normalize_inventory(
        '[{"ProcessId":4,"Name":"System","CommandLine":null},'
        '{"ProcessId":9,"Name":"a.exe","CommandLine":"a.exe -x"}]')
    assert ok[0]["cmdline_available"] is False and ok[1]["cmdline_available"] is True


@case("L-D2 a failed F8 refuses BEFORE any HTTP call or run-tree creation")
def _():
    import requests

    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        original = cap.TMP_ROOT
        cap.TMP_ROOT = d / "tmp"
        opened = []

        class NeverCalled:
            def __init__(self, *a, **k):
                pass

            def __call__(self, url, *, timeout, allow_redirects):
                opened.append(url)
                raise AssertionError("a request was issued despite a failed pre-flight")

        try:
            run_obj = cap.SmokeRun("20260907T010000Z", evidence_root=d / "ev")
            try:
                run_obj.capture(
                    session=requests.Session(), requests_module=requests,
                    process_lister=lambda: [],          # unavailable -> F8 FAIL
                    transport_factory=NeverCalled, supervise_jobs=False,
                    reference_reader=lambda: build_extract({}))
            except cap.PreflightError as exc:
                assert "F8" in str(exc), str(exc)
            else:
                raise AssertionError("capture ran with a failed F8")
        finally:
            cap.TMP_ROOT = original
        assert opened == [], opened
        assert not (d / "tmp").exists(), "a run tree was created despite a failed F8"
        assert not (d / "ev").exists(), "an evidence tree was created despite a failed F8"


@case("L-D2 no code path in the smoke starts or stops a process")
def _():
    import re as _re

    source = (HERE / "smoke_capture.py").read_text(encoding="utf-8")
    # These have no legitimate use here at all, not even as text.
    for forbidden in ("taskkill", "os.kill", "terminate()", "Start-Service",
                      "Stop-Service", "Restart-Service"):
        assert forbidden not in source, forbidden
    # A process-starting verb may appear ONLY as a detection pattern - D2 has to
    # recognise `Start-Process` to catch a launcher - and never in a string this module
    # executes. Every occurrence must sit on a `re.compile(...)` line or a comment.
    for verb in ("Start-Process", "Stop-Process"):
        for number, line in enumerate(source.splitlines(), 1):
            if verb in line:
                assert "re.compile(" in line or line.lstrip().startswith("#"), \
                    "%s used outside a detection pattern at line %d: %s" % (verb, number, line)
    # the only subprocess calls are the read-only inventory and git provenance
    calls = _re.findall(r"subprocess\.run\(\s*\[([^\]]*)\]", source)
    for call in calls:
        head = call.split(",")[0].strip().strip('"\'')
        assert head in ("git", "ps", "powershell"), head
    # and the one PowerShell program this module executes is read-only
    assert "Get-CimInstance" in cap._INVENTORY_PS
    for mutating in ("Start-", "Stop-", "Set-", "Remove-", "New-Item", "Invoke-Expression"):
        assert mutating not in cap._INVENTORY_PS.replace("New-Object System.Text", ""), mutating



# ======== M: the three D2 gaps reproduced by M2B_D1D2_CODEX_REVIEW.md, all synthetic ====
# Every record below is hand-written. Nothing is launched, nothing is stopped, and no
# real process is inspected: these drive the real `preflight()` F8 through a fake lister.

def normalized(*records):
    """Push raw CIM-shaped records through the real normalizer, as the reviewer did."""
    return cap._normalize_inventory(json.dumps(list(records)))


@case("M-P1a a blank or whitespace command line on a stack image is not evidence")
def _():
    for raw in ("", "   ", "\t\n"):
        items = normalized({"ProcessId": 999991, "Name": "python.exe", "CommandLine": raw})
        assert items[0]["cmdline_available"] is False, raw
        check = f8_status(quiet_lister() + items)
        assert check.status == "FAIL", (raw, check.detail)
        assert "unproven" in check.detail, check.detail


@case("M-P1a a record with neither a usable name nor a command line is ambiguous")
def _():
    items = normalized({"ProcessId": 999991, "CommandLine": None})
    check = f8_status(quiet_lister() + items)
    assert check.status == "FAIL", check.detail
    assert check.data["unreadable_relevant"][0]["pid"] == 999991, check.data
    items = normalized({"ProcessId": 999992, "Name": "   ", "CommandLine": ""})
    assert f8_status(quiet_lister() + items).status == "FAIL"


@case("M-P1a the legitimate System/null-command record is still unrelated")
def _():
    items = normalized({"ProcessId": 4, "Name": "System", "CommandLine": None},
                       {"ProcessId": 92, "Name": "Registry", "CommandLine": None})
    assert all(i["cmdline_available"] is False for i in items)
    assert f8_status(quiet_lister() + items).status == "PASS"


@case("M-P1a a non-string Name or CommandLine is refused by the normalizer")
def _():
    for bad in ({"ProcessId": 1, "Name": 5, "CommandLine": "x"},
                {"ProcessId": 1, "Name": "x", "CommandLine": 7}):
        try:
            normalized(bad)
        except cap.InventoryUnavailable as exc:
            assert "non-string" in str(exc), str(exc)
        else:
            raise AssertionError("accepted %r" % bad)


@case("M-P1b backend-relative worker launches are recognised")
def _():
    relative = [
        r"python.exe -X utf8 scripts\control_plane_loop.py --profile full",
        r"python.exe -X utf8 scripts\market_history_refresh_loop.py",
        "python.exe -X utf8 scripts/capital_flow_refresh_loop.py",
        "python.exe codex_market_pulse.py --api-base http://127.0.0.1:8000",
    ]
    for command in relative:
        check = f8_status(quiet_lister() + [
            {"pid": 4242, "name": "python.exe", "cmdline": command,
             "cmdline_available": True}])
        assert check.status == "FAIL", (command, check.detail)
        assert "appears to be running" in check.detail, command


@case("M-P1b naming a worker without an interpreter is still not a launch")
def _():
    for image, command in (
            ("code.exe", r"code.exe D:\p\backend\scripts\control_plane_loop.py"),
            ("notepad.exe", r"notepad.exe scripts\control_plane_loop.py"),
            ("explorer.exe", "explorer.exe control_plane_loop.py")):
        check = f8_status(quiet_lister() + [
            {"pid": 4243, "name": image, "cmdline": command, "cmdline_available": True}])
        assert check.status == "PASS", (command, check.detail)


@case("M-P1c inline execution of the API or the launcher is recognised")
def _():
    cases = [
        ("python.exe",
         "python.exe -c \"import uvicorn; uvicorn.run('app.main:app', host='127.0.0.1', "
         "port=8000)\""),
        ("powershell.exe",
         "powershell.exe -NoProfile -Command \"& 'D:\\p\\scripts\\run_stack.ps1'\""),
        ("python.exe",
         "python.exe -c \"import runpy; runpy.run_path('scripts/control_plane_loop.py')\""),
        ("powershell.exe",
         "powershell.exe -Command \"Start-Process python -ArgumentList '-m','uvicorn'\""),
    ]
    for image, command in cases:
        check = f8_status(quiet_lister() + [
            {"pid": 4244, "name": image, "cmdline": command, "cmdline_available": True}])
        assert check.status == "FAIL", (command, check.detail)


@case("M-P1c a literal print or a listing verb is still not a launch")
def _():
    cases = [
        ("python.exe", "python.exe -c \"print('-m uvicorn app.main:app')\""),
        ("powershell.exe", 'powershell.exe -Command "Get-Item scripts/run_stack.ps1"'),
        ("powershell.exe", 'powershell.exe -Command "Select-String uvicorn app.main:app"'),
        ("bash.exe", 'bash.exe -c "grep -n uvicorn backend/scripts/control_plane_loop.py"'),
    ]
    for image, command in cases:
        check = f8_status(quiet_lister() + [
            {"pid": 4245, "name": image, "cmdline": command, "cmdline_available": True}])
        assert check.status == "PASS", (command, check.detail)


@case("M-P1c an inline program that names a target but cannot be read is ambiguous")
def _():
    unresolved = [
        ("python.exe", "python.exe -c \"cfg = load(); boot(cfg, 'app.main:app')\""),
        ("powershell.exe", 'powershell.exe -Command "$s = \'run_stack.ps1\'; go $s"'),
        ("python.exe", "python.exe -c \"%s\"" % ("uvicorn " * 900)),
    ]
    for image, command in unresolved:
        check = f8_status(quiet_lister() + [
            {"pid": 4246, "name": image, "cmdline": command, "cmdline_available": True}])
        assert check.status == "FAIL", (command[:60], check.detail)
        assert "unproven" in check.detail or "appears to be running" in check.detail


@case("M-P1c an inline program naming nothing relevant stays unrelated")
def _():
    for command in ('python.exe -c "print(1+1)"',
                    'powershell.exe -Command "Get-Date"',
                    'bash.exe -c "ls -la /tmp"'):
        image = command.split(".exe")[0] + ".exe"
        check = f8_status(quiet_lister() + [
            {"pid": 4247, "name": image, "cmdline": command, "cmdline_available": True}])
        assert check.status == "PASS", (command, check.detail)


@case("M each reviewer counterexample now fails F8 through the real preflight")
def _():
    # The exact seven records M2B_D1D2_CODEX_REVIEW.md reproduced.
    seven = [
        ("backend-relative control worker", "python.exe",
         r"python.exe -X utf8 scripts\control_plane_loop.py --profile full"),
        ("backend-relative history worker", "python.exe",
         r"python.exe -X utf8 scripts\market_history_refresh_loop.py"),
        ("inline executing API", "python.exe",
         "python.exe -c \"import uvicorn; uvicorn.run('app.main:app', host='127.0.0.1', "
         "port=8000)\""),
        ("inline executing stack launcher", "powershell.exe",
         "powershell.exe -NoProfile -Command \"& 'D:\\p\\scripts\\run_stack.ps1'\""),
    ]
    for label, image, command in seven:
        check = f8_status(quiet_lister() + [
            {"pid": 999991, "name": image, "cmdline": command, "cmdline_available": True}])
        assert check.status == "FAIL", (label, check.detail)
    for label, record in (
            ("normalized empty command on python",
             {"ProcessId": 999991, "Name": "python.exe", "CommandLine": ""}),
            ("normalized whitespace command on python",
             {"ProcessId": 999991, "Name": "python.exe", "CommandLine": "  "}),
            ("normalized missing name and null command",
             {"ProcessId": 999991, "CommandLine": None})):
        try:
            items = normalized(record)
            status = f8_status(quiet_lister() + items).status
        except cap.InventoryUnavailable:
            status = "FAIL"
        assert status == "FAIL", label


@case("M a failed F8 from an ambiguous record refuses before HTTP or run-tree creation")
def _():
    import requests

    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        original = cap.TMP_ROOT
        cap.TMP_ROOT = d / "tmp"
        issued = []

        class NeverCalled:
            def __init__(self, *a, **k):
                pass

            def __call__(self, url, *, timeout, allow_redirects):
                issued.append(url)
                raise AssertionError("a request was issued despite a failed F8")

        def ambiguous_lister():
            # a python process whose command line cannot be read: unproven, not absent
            return quiet_lister() + cap._normalize_inventory(json.dumps(
                [{"ProcessId": 999991, "Name": "python.exe", "CommandLine": ""}]))

        try:
            run_obj = cap.SmokeRun("20260907T010000Z", evidence_root=d / "ev")
            try:
                run_obj.capture(session=requests.Session(), requests_module=requests,
                                process_lister=ambiguous_lister,
                                transport_factory=NeverCalled, supervise_jobs=False,
                                reference_reader=lambda: build_extract({}))
            except cap.PreflightError as exc:
                assert "F8" in str(exc) and "unproven" in str(exc), str(exc)
            else:
                raise AssertionError("capture ran with an ambiguous process inventory")
        finally:
            cap.TMP_ROOT = original
        assert issued == [], issued
        assert not (d / "tmp").exists(), "a run tree was created despite a failed F8"
        assert not (d / "ev").exists(), "an evidence tree was created despite a failed F8"



# ===== N: the whole-program / literal boundary (M2B_D2_LITERAL_BOUNDARY_CODEX_REVIEW) ===
# A harmless PREFIX is not a harmless program. Every record is synthetic data; no command
# text is ever executed, and `ast.parse` builds a tree without running anything.

@case("N-P1 a harmless prefix does not make a compound program harmless")
def _():
    compound = [
        ("python.exe",
         "python.exe -c \"print('starting'); from uvicorn import run; run('app.main:app')\""),
        ("powershell.exe",
         'powershell.exe -Command "Get-Item .; python.exe scripts/control_plane_loop.py"'),
        ("powershell.exe",
         'powershell.exe -Command "Get-Item $(python.exe scripts/control_plane_loop.py)"'),
    ]
    for image, command in compound:
        check = f8_status(quiet_lister() + [
            {"pid": 5551, "name": image, "cmdline": command, "cmdline_available": True}])
        assert check.status == "FAIL", (command, check.detail)


@case("N-P2 a literal print of launch-looking text is not a launch")
def _():
    check = f8_status(quiet_lister() + [
        {"pid": 5552, "name": "python.exe",
         "cmdline": "python.exe -c \"print('uvicorn.run(app.main:app)')\"",
         "cmdline_available": True}])
    assert check.status == "PASS", check.detail
    verdict, why = cap.classify_process(
        {"name": "python.exe",
         "cmdline": "python.exe -c \"print('uvicorn.run(app.main:app)')\"",
         "cmdline_available": True})
    assert verdict == "other" and "provably inert" in why, (verdict, why)


@case("N the Python inertness proof covers the whole program, not its first statement")
def _():
    inert = [
        "print('uvicorn.run(app.main:app)')",
        "print('a'); print('b')",
        "print('x', 'app.main:app', sep=', ')",
        "repr('run_stack.ps1')",
        "print(['app.main:app', 1, None])",
        "'app.main:app'",
    ]
    for program in inert:
        ok, why = cap._python_program_is_inert(program)
        assert ok, (program, why)
    not_inert = [
        "print('starting'); from uvicorn import run; run('app.main:app')",
        "import uvicorn",
        "x = 'app.main:app'",
        "os.system('run_stack.ps1')",
        "print(open('run_stack.ps1').read())",
        "print(uvicorn)",
        "for i in range(3): print('app.main:app')",
        "print('a'" ,
        "exec('uvicorn.run()')",
        "__import__('uvicorn').run('app.main:app')",
    ]
    for program in not_inert:
        ok, why = cap._python_program_is_inert(program)
        assert not ok, (program, why)


@case("N the PowerShell inertness proof refuses sequencing, substitution and variables")
def _():
    inert = ["Get-Item scripts/run_stack.ps1", "Select-String uvicorn app.main:app",
             "Get-Content run_stack.ps1", "  ls  scripts/run_stack.ps1  "]
    for program in inert:
        ok, why = cap._ps_program_is_inert(program)
        assert ok, (program, why)
    not_inert = [
        "Get-Item .; python.exe scripts/control_plane_loop.py",
        "Get-Item $(python.exe scripts/control_plane_loop.py)",
        "Get-Item run_stack.ps1 | Invoke-Expression",
        "& 'run_stack.ps1'",
        "Get-Item $script",
        "Start-Process python",
        "Get-Item a `n Get-Item b",
        "python.exe -m uvicorn app.main:app",
    ]
    for program in not_inert:
        ok, why = cap._ps_program_is_inert(program)
        assert not ok, (program, why)


@case("N an unprovable relevant program is ambiguous, never harmless")
def _():
    for image, command, python in (
            ("python.exe", "python.exe -c \"boot('app.main:app')\"", True),
            ("powershell.exe", 'powershell.exe -Command "go run_stack.ps1"', False)):
        verdict, why = cap.classify_process(
            {"name": image, "cmdline": command, "cmdline_available": True})
        assert verdict == "ambiguous", (command, verdict, why)
        assert "could not be proven inert" in why, why


@case("N the inertness proof parses but never executes the program")
def _():
    # A program whose execution would be observable; parsing it must change nothing.
    marker = HERE / "__n_block_must_not_exist__.tmp"
    program = "print(open(%r, 'w').write('x'))" % str(marker)
    ok, _why = cap._python_program_is_inert(program)
    assert ok is False
    assert not marker.exists(), "the inertness check executed the program"


@case("N the four literal-boundary counterexamples resolve as the reviewer requires")
def _():
    expected = [
        ("python.exe", "python.exe -c \"print('uvicorn.run(app.main:app)')\"", "PASS"),
        ("python.exe",
         "python.exe -c \"print('starting'); from uvicorn import run; run('app.main:app')\"",
         "FAIL"),
        ("powershell.exe",
         'powershell.exe -Command "Get-Item .; python.exe scripts/control_plane_loop.py"',
         "FAIL"),
        ("powershell.exe",
         'powershell.exe -Command "Get-Item $(python.exe scripts/control_plane_loop.py)"',
         "FAIL"),
    ]
    for image, command, want in expected:
        check = f8_status(quiet_lister() + [
            {"pid": 5553, "name": image, "cmdline": command, "cmdline_available": True}])
        assert check.status == want, (command, want, check.detail)



# ====== O: R2-A/B/C, driven by the five responses retained by run 20260908T082833Z ======
# Referenced by SHA-256 so a substituted file fails rather than passes. Never modified.

RUN2 = HERE / "evidence_20260908T082833Z" / "raw"
RUN2_BODIES = {
    "01": ("01_sh600011_klc_kl.js.bin",
           "adc5a39131ba32df3bdc53cbc47bcc842f9ed2c31c8e60cfe8173f2d387a2d02"),
    "02": ("02_sh600011_getAmountBySymbol.bin",
           "9112ebac1d613c42" ),
    "03": ("03_sh000300_klc_kl.js.bin",
           "ef2180be45a1c1bb33f99772a55b410eb3923524d9b8fe268d549584a6e28647"),
    "04": ("04_bj920000_klc_kl.js.bin", "100d3b527b963ebd"),
    "05": ("05_bj920000_getAmountBySymbol.bin", "2ab669b3ec2d245e"),
}


def run2_body(key):
    name, digest = RUN2_BODIES[key]
    path = RUN2 / name
    if not path.exists():
        raise AssertionError("retained run-2 body %s is missing" % name)
    raw = path.read_bytes()
    assert hashlib.sha256(raw).hexdigest().startswith(digest), "retained body %s changed" % name
    return raw


@case("O-R2A the real auxiliary object-array bodies now parse, zeros preserved")
def _():
    rows = dec.parse_outstanding_share(run2_body("02"), None,
                                       expected_symbol="sh600011")
    assert len(rows) == 26, len(rows)
    assert rows[0]["date"] == "2001-12-06" and rows[-1]["date"] == "2019-10-15"
    assert all(r["usable"] for r in rows), "SH600011 has no zero observations"
    assert rows[-1]["outstanding_share_wan"] == 1099770.9919, rows[-1]

    rows = dec.parse_outstanding_share(run2_body("05"), None,
                                       expected_symbol="bj920000")
    assert len(rows) == 42, len(rows)
    zeros = [r for r in rows if not r["usable"]]
    assert [r["date"] for r in zeros] == ["2015-03-06", "2015-09-15"], zeros
    assert all(r["outstanding_share_wan"] == 0 for r in zeros), zeros
    # kept in the series, not dropped
    assert len(rows) == 42 and rows[0]["date"] == "2015-03-06"


@case("O-R2A the zero observations are never used as a denominator, and never backfilled")
def _():
    rows = dec.parse_outstanding_share(run2_body("05"), None, expected_symbol="bj920000")
    # both zeros precede the pinned window; the value in force there is a later positive
    at_window = dec.outstanding_share_as_of(rows, cap.WINDOW_START)
    assert at_window is not None and at_window["outstanding_share_wan"] > 0, at_window
    assert at_window["date"] <= cap.WINDOW_START
    # as-of a zero's own date returns nothing usable, rather than a later value
    assert dec.outstanding_share_as_of(rows, "2015-03-06") is None
    assert dec.outstanding_share_as_of(rows, "2015-09-15") is None
    # ... and never a value dated after the asked-for date
    for probe in ("2015-10-27", "2020-01-01", cap.WINDOW_END):
        found = dec.outstanding_share_as_of(rows, probe)
        if found:
            assert found["date"] <= probe, (probe, found)


@case("O-R2A a step series with no in-window observation still covers the window")
def _():
    rows = dec.parse_outstanding_share(run2_body("02"), None, expected_symbol="sh600011")
    quality = dec.share_series_quality(rows, (cap.WINDOW_START, cap.WINDOW_END))
    # SH600011's last observation is 2019-10-15, before the window opens
    assert quality["entries_in_window"] == 0, quality
    assert quality["entries_before_window"] == 26, quality
    assert quality["covers_window_start"] is True, quality
    assert quality["value_in_force_at_window_start"] == 1099770.9919, quality
    assert quality["is_traded_amount"] is False and "万股" in quality["unit"]

    rows = dec.parse_outstanding_share(run2_body("05"), None, expected_symbol="bj920000")
    quality = dec.share_series_quality(rows, (cap.WINDOW_START, cap.WINDOW_END))
    assert quality["entries_in_window"] == 7, quality
    assert len(quality["unusable_entries"]) == 2, quality


@case("O-R2A the auxiliary parser binds the symbol and refuses a foreign body")
def _():
    try:
        dec.parse_outstanding_share(run2_body("02"), None, expected_symbol="bj920000")
    except dec.DecodeError as exc:
        assert "does not match the expected" in str(exc), str(exc)
    else:
        raise AssertionError("SH600011's body was accepted as BJ920000's")


@case("O-R2A the XSS-guard comment is data, and a mixed-shape array is refused")
def _():
    guarded = jsonp_body("sh600011", [("2024-01-02", 5.0)], shape="object", guard=True)
    assert b"<script>" in guarded
    rows = dec.parse_outstanding_share(guarded, "utf-8", expected_symbol="sh600011")
    assert rows == [{"date": "2024-01-02", "outstanding_share_wan": 5.0,
                     "usable": True, "unusable_reason": None}], rows
    # the legacy pair form still parses
    pairs = jsonp_body("sh600011", [("2024-01-02", 5.0)], shape="pair", guard=False)
    assert dec.parse_outstanding_share(pairs, "utf-8", expected_symbol="sh600011")[0][
        "outstanding_share_wan"] == 5.0
    mixed = b'var KKE_ShareAmount_sh600011=([{"date":"2024-01-02","amount":1},["2024-01-03",2]]);'
    try:
        dec.parse_outstanding_share(mixed, "utf-8", expected_symbol="sh600011")
    except dec.DecodeError as exc:
        assert "homogeneous" in str(exc), str(exc)
    else:
        raise AssertionError("a mixed-shape array was accepted")


@case("O-R2B the complete variable name is validated against exchange and symbol")
def _():
    assert dec.expected_js_variable("klc", "stock", "sh600011") == "KLC_K2_sh600011"
    assert dec.expected_js_variable("klc", "benchmark", "sh000300") == "KLC_KL_sh000300"
    assert dec.expected_js_variable("outstanding_share", "stock",
                                    "bj920000") == "KKE_ShareAmount_bj920000"
    good = [("KLC_K2_sh600011", "klc", "stock", "sh600011"),
            ("KLC_K2_bj920000", "klc", "stock", "bj920000"),
            ("KLC_KL_sh000300", "klc", "benchmark", "sh000300")]
    for name, kind, klass, sym in good:
        ok, why = dec.check_js_variable(name, kind, klass, sym)
        assert ok, (name, why)
    bad = [
        ("KLC_K2_sh600012", "klc", "stock", "sh600011"),   # wrong symbol
        ("KLC_K2_sz600011", "klc", "stock", "sh600011"),   # wrong exchange
        ("KLC_KL_sh600011", "klc", "stock", "sh600011"),   # index prefix on a stock
        ("KLC_K2_sh000300", "klc", "benchmark", "sh000300"),  # stock prefix on the index
        ("KKE_ShareAmount_sh600011", "klc", "stock", "sh600011"),  # wrong family
        ("klc_kl_sh600011", "klc", "stock", "sh600011"),   # the old synthetic name
        ("KLC_K2_sh600011_extra", "klc", "stock", "sh600011"),
    ]
    for name, kind, klass, sym in bad:
        ok, why = dec.check_js_variable(name, kind, klass, sym)
        assert not ok, (name, why)
        assert "does not match the expected" in why


@case("O-R2B the retained bodies carry exactly the expected variable names")
def _():
    import re as _re

    for key, kind, klass, sym in (("01", "klc", "stock", "sh600011"),
                                  ("03", "klc", "benchmark", "sh000300"),
                                  ("04", "klc", "stock", "bj920000"),
                                  ("02", "outstanding_share", "stock", "sh600011"),
                                  ("05", "outstanding_share", "stock", "bj920000")):
        text = run2_body(key).decode("utf-8")
        name = _re.search(r"var\s+(\w+)\s*=", text).group(1)
        ok, why = dec.check_js_variable(name, kind, klass, sym)
        assert ok, (key, name, why)
    # and the digit-collection bug is gone: these no longer decide anything
    assert "".join(c for c in "KLC_K2_sh600011" if c.isdigit()) == "2600011"
    assert dec.check_js_variable("KLC_K2_sh600011", "klc", "stock", "sh600011")[0]


@case("O-R2C the replay window is passed explicitly, not as empty strings")
def _():
    assert chk.REPLAY_START == "20220824" and chk.REPLAY_END == "20260904"
    source = (HERE / "smoke_checks.py").read_text(encoding="utf-8")
    assert '(job["adapter_symbol"], "", "")' not in source, "empty replay dates remain"
    assert "REPLAY_START, REPLAY_END" in source


@case("O-R2C an unevaluated job is distinguishable from a failed one")
def _():
    status, detail = chk._replay_verdict({}, [], True, None)
    assert status == chk.INCONCLUSIVE and "NOT EVALUATED" in detail
    assert "captured but could not be parsed" in detail
    assert "not a failed one" in detail
    status, detail = chk._replay_verdict({}, [], False, "TypeError: boom")
    assert status == chk.INCONCLUSIVE and "did not complete for any job" in detail
    # a real result with rows and dates passes; one without rows FAILS rather than passes
    dates = ["2022-08-24", "2023-01-03", "2026-09-04"]
    ok = {"rows": 3, "first_date": dates[0], "last_date": dates[-1], "dates": dates}
    assert chk._replay_verdict(ok, [], False, None)[0] == chk.PASS
    assert chk._replay_verdict({"rows": 0, "first_date": None}, [], False, None)[0] == chk.FAIL
    assert chk._replay_verdict(ok, ["2099-01-01"], False, None)[0] == chk.FAIL


@case("O-R2C C4 reports absence of measurement, never a measured zero loss")
def _():
    with tempfile.TemporaryDirectory() as d:
        # a scene whose auxiliary bodies are unparseable, so the share series is absent
        scene = scenario(d, specs={2: {"outcome": "ok", "body": b'var KKE_ShareAmount_sh600011=([{"nope":1}]);'}})
        det = run(scene)["deterministic"]
        c4 = [c for c in det["checks"] if c["id"] == "C4" and c["symbol"] == "sh600011"][0]
        assert c4["measured"]["share_series_available"] is False, c4
        assert "NOT MEASURED" in c4["detail"], c4["detail"]
        assert "not a measured zero loss" in c4["detail"], c4["detail"]
        assert "klc_rows_before_first_usable_share" not in c4["measured"], c4


# ============ P: the R2-ABC closure - denominator validity and R1 hardening ============
# C1: an explicit invalid observation must INTERRUPT denominator validity. The previous
# as-of skipped it and silently restored an older positive count across it.

PZP = [("2020-01-01", 100.0), ("2020-01-03", 0.0), ("2020-01-05", 200.0)]


def share_rows(series, symbol="sh600011"):
    return dec.parse_outstanding_share(jsonp_body(symbol, series), None,
                                       expected_symbol=symbol)


@case("P-C1 an explicit zero interrupts the denominator until a later valid observation")
def _():
    rows = share_rows(PZP)
    assert [r["outstanding_share_wan"] for r in rows] == [100.0, 0.0, 200.0], rows
    assert [r["usable"] for r in rows] == [True, False, True], rows

    def wan(date):
        found = dec.outstanding_share_as_of(rows, date)
        return found["outstanding_share_wan"] if found else None

    # before the series: never backfilled from a later observation
    assert wan("2019-12-31") is None
    # the positive value is in force up to the day before the zero
    assert wan("2020-01-01") == 100.0 and wan("2020-01-02") == 100.0
    # the zero's own date and every day it remains in force yield NO denominator -
    # the older 100.0 is NOT restored across it
    assert wan("2020-01-03") is None, "the zero was skipped and 100.0 restored"
    assert wan("2020-01-04") is None, "an older count was restored across the zero"
    # a later valid observation restores validity, and carries forward from there
    assert wan("2020-01-05") == 200.0 and wan("2020-01-06") == 200.0

    # the zero is preserved as evidence, with its reason, not discarded
    state = dec.share_state_as_of(rows, "2020-01-04")
    assert state["date"] == "2020-01-03" and state["outstanding_share_wan"] == 0.0
    assert state["usable"] is False and state["unusable_reason"], state
    assert dec.share_state_as_of(rows, "2019-12-31") is None


@case("P-C1 repeated zeros and a trailing zero stay invalid, with reported intervals")
def _():
    rows = share_rows([("2020-01-01", 100.0), ("2020-01-03", 0.0),
                       ("2020-01-04", 0.0), ("2020-01-06", 200.0)])
    for date in ("2020-01-03", "2020-01-04", "2020-01-05"):
        assert dec.outstanding_share_as_of(rows, date) is None, date
    assert dec.outstanding_share_as_of(rows, "2020-01-06")["outstanding_share_wan"] == 200.0
    spans = dec.invalid_denominator_intervals(rows)
    assert [(x["from"], x["until"]) for x in spans] == [
        ("2020-01-03", "2020-01-06"), ("2020-01-04", "2020-01-06")], spans
    assert all(x["reason"] for x in spans), spans

    # a series that ENDS unusable has no denominator from that date on, forever
    tail = share_rows([("2020-01-01", 100.0), ("2020-01-05", 0.0)])
    assert dec.outstanding_share_as_of(tail, "2020-01-04")["outstanding_share_wan"] == 100.0
    for date in ("2020-01-05", "2020-06-30", "2026-09-04"):
        assert dec.outstanding_share_as_of(tail, date) is None, date
    assert dec.invalid_denominator_intervals(tail) == [
        {"from": "2020-01-05", "until": None,
         "reason": "the vendor reports zero shares on this date"}]


@case("P-C1 coverage cannot bridge an invalid observation, and matches pandas ffill")
def _():
    rows = share_rows(PZP)
    q = dec.share_series_quality(rows, ("2020-01-04", "2020-01-05"))
    assert q["covers_window_start"] is False, q
    assert q["value_in_force_at_window_start"] is None, q
    assert q["carry_in_age_days_at_window_start"] is None, q
    # the withheld zero stays VISIBLE rather than reading as an absent observation
    assert q["state_at_window_start"]["outstanding_share_wan"] == 0.0, q
    assert q["state_at_window_start"]["usable"] is False, q
    assert q["invalid_denominator_intervals"] == [
        {"from": "2020-01-03", "until": "2020-01-05",
         "reason": "the vendor reports zero shares on this date"}], q
    # a window opening on the restoring observation is covered again
    q2 = dec.share_series_quality(rows, ("2020-01-05", "2020-01-06"))
    assert q2["covers_window_start"] is True and q2["value_in_force_at_window_start"] == 200.0
    assert q2["carry_in_age_days_at_window_start"] == 0, q2

    # the installed pandas keeps an explicit zero rather than the older positive value,
    # which is the behaviour the as-of now reproduces (the old docstring claimed the
    # opposite equivalence).
    filled = pandas.Series([100.0, 0.0, None, 200.0]).ffill().tolist()
    assert filled == [100.0, 0.0, 0.0, 200.0], filled
    by_ffill = dict(zip(["2020-01-01", "2020-01-03", "2020-01-04", "2020-01-05"], filled))
    for date, value in by_ffill.items():
        found = dec.outstanding_share_as_of(rows, date)
        assert (found["outstanding_share_wan"] if found else None) == (value or None), date


@case("P-C1 U4 counts rows under an invalid observation apart, end to end")
def _():
    research_dates = [d for d in WINDOW if cap.RESEARCH_START <= d <= cap.RESEARCH_END]
    zero_date, restore_date = research_dates[10], research_dates[30]
    series = [(WINDOW[0], 250_000.0), (zero_date, 0.0), (restore_date, 250_000.0)]
    with tempfile.TemporaryDirectory() as d:
        scene = scenario(d, specs={2: {"outcome": "ok",
                                       "body": jsonp_body("sh600011", series)}})
        det = run(scene)["deterministic"]
        u4 = [c for c in det["checks"] if c["id"] == "U4" and c["symbol"] == "sh600011"][0]
        m = u4["measured"]
        blocked = [d2 for d2 in research_dates if zero_date <= d2 < restore_date]
        assert m["rows_under_an_invalid_observation"] == len(blocked) == 20, m
        assert m["rows_before_the_first_observation"] == 0, m
        assert m["rows_without_applicable_share"] == len(blocked), m
        assert m["aligned_rows"] == len(research_dates) - len(blocked), m
        assert m["invalid_denominator_intervals"] == [
            {"from": zero_date, "until": restore_date,
             "reason": "the vendor reports zero shares on this date"}], m
        assert "while an explicit invalid observation was in force" in u4["detail"]
        # D5 still reports the series it did receive; U4 is advisory, never a FAIL
        assert u4["status"] == chk.ADVISORY, u4
        d5 = [c for c in det["checks"] if c["id"] == "D5" and c["symbol"] == "sh600011"][0]
        assert d5["status"] == chk.PASS and d5["measured"]["entries"] == 3, d5


@case("P-C2 R1 rejects row counts and first/last metadata with no actual dates")
def _():
    forged = {"rows": 1, "first_date": "2023-01-03", "last_date": None, "dates": []}
    status, detail = chk._replay_verdict(forged, [], False, None)
    assert status == chk.FAIL, (status, detail)
    assert "no actual date sequence was returned" in detail, detail

    dates = ["2023-01-03", "2023-01-04", "2023-01-05"]
    good = {"rows": 3, "first_date": dates[0], "last_date": dates[-1], "dates": dates}
    assert chk._replay_verdict(good, [], False, None)[0] == chk.PASS

    bad = [
        (dict(good, rows=978), "disagrees with the 3 dates actually returned"),
        (dict(good, first_date="2023-01-02"), "disagrees with the returned sequence"),
        (dict(good, last_date=None), "disagrees with the returned sequence"),
        (dict(good, rows=4, dates=dates + ["2023-01-05"]), "repeats 1 dates"),
        (dict(good, dates=["2023-01-05", "2023-01-04", "2023-01-03"],
              first_date="2023-01-05", last_date="2023-01-03"),
         "not in ascending order"),
    ]
    for info, expected in bad:
        status, detail = chk._replay_verdict(info, [], False, None)
        assert status == chk.FAIL, (info, detail)
        assert expected in detail, (expected, detail)


@case("P-C2 the declared stock window binds the stock replay, not the index interface")
def _():
    outside = ["2019-01-02", "2023-01-03"]
    info = {"rows": 2, "first_date": outside[0], "last_date": outside[-1],
            "dates": outside}
    status, detail = chk._replay_verdict(info, [], False, None)
    assert status == chk.FAIL and "outside the declared window" in detail, detail
    assert cap.WINDOW_START in detail and cap.WINDOW_END in detail, detail
    # the index adapter takes no date arguments and returns its full served series, so
    # the stock window is NOT imposed on it
    status, detail = chk._replay_verdict(info, [], False, None, window=None,
                                         label="index adapter")
    assert status == chk.PASS, detail
    assert "no date arguments" in detail and "index adapter returned" in detail, detail
    # ... and the sequence checks still apply to it
    assert chk._replay_verdict({"rows": 2, "first_date": outside[0], "last_date": None,
                                "dates": []}, [], False, None, window=None)[0] == chk.FAIL


@case("P-C2 the real checks keep the two interfaces apart on a full scenario")
def _():
    with tempfile.TemporaryDirectory() as d:
        det = run(scenario(d))["deterministic"]
        r1 = {c["symbol"]: c for c in det["checks"] if c["id"] == "R1"}
        for name in ("sh600011", "bj920000", "sh000300"):
            assert r1[name]["status"] == chk.PASS, r1[name]
            assert r1[name]["measured"]["dates_returned"] == r1[name]["measured"]["rows"]
        assert "declared window" in r1["sh600011"]["detail"]
        assert "no date arguments" in r1["sh000300"]["detail"]
        assert r1["sh000300"]["threshold"]["window"] == "not applicable to the index interface"
        assert r1["sh600011"]["threshold"]["window"].endswith(
            "(dates within %s..%s)" % (cap.WINDOW_START, cap.WINDOW_END))


def main():
    failures = 0
    print("M2b offline smoke test suite (no remote connection, no production write)")
    for name, fn in CASES:
        try:
            fn()
            print("  [ok] %s" % name)
        except AssertionError as exc:
            failures += 1
            print("  [XX] %s\n       %s" % (name, str(exc)[:500]))
        except Exception as exc:                      # noqa: BLE001
            failures += 1
            print("  [XX] %s\n       unexpected %s: %s"
                  % (name, type(exc).__name__, str(exc)[:500]))
    print("\n  %d cases, %d unexpected" % (len(CASES), failures))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
