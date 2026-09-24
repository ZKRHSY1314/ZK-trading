"""M2b P-C - Section 6 as executable checks, one outcome table, and a frozen replay.

What this module is for
-----------------------
Everything here consumes ONLY retained evidence: the captured `raw/*.bin`, the capture
manifest, and the reference extract frozen at capture time. It never opens a production
database - `replay()` installs `db_guard()` so that is enforced, not promised (S3).

The outcome table (S2)
----------------------
`OUTCOME_TABLE` is the single place where "what happened on the wire" becomes "what that
means". It is exhaustive over `(transport_state, payload_state)` and it decides, in one
step: the request result, the job result, the evidence class, whether the job's remaining
requests are skipped, and whether the run aborts. Two properties follow by construction:

* a transport failure, a decoder error, an empty body or markup can NEVER become a
  positive capability finding. They are `FAILED` or `INCONCLUSIVE_*` evidence;
* the only route to "the vendor does not serve this path" is an explicit, authenticated,
  non-retryable vendor answer - HTTP 404 or 410. Even then the finding is
  `vendor_explicit_absence_at_path`, and its CAUSE (a `92xxxx` code mapping, a retired
  path, something else) is recorded as NOT ESTABLISHED, because five responses cannot
  establish it.

The request-count check reads the same table, so the number of requests issued and the
outcomes always agree: a skipped request is skipped because the table said so.

Verdict values
--------------
`PASS`, `PASS_WITH_DOCUMENTED_BJ_NON_SERVICE`, `INCONCLUSIVE`, `FAIL`. The second is
deliberately NOT an unqualified PASS: it records a completed investigation with a
documented BJ limitation, and it authorizes nothing - least of all the 52-symbol pilot.
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import json
import sys
import time
from pathlib import Path

SMOKE_DIR = Path(__file__).resolve().parent
REPO_ROOT = SMOKE_DIR.parents[1]
sys.path.insert(0, str(SMOKE_DIR))
sys.path.insert(0, str(REPO_ROOT / "claude methods" / "_m2_pilot"))
sys.path.insert(0, str(REPO_ROOT / "claude methods" / "_m1_closure"))

import sina_klc_decoder as dec                        # noqa: E402
import smoke_capture as cap                           # noqa: E402
import smoke_outcomes as out                          # noqa: E402  (the shared table)
import provenance as prov                             # noqa: E402  (unchanged M2a)
import transport as tp                                # noqa: E402  (unchanged M2a)

# The outcome table now lives in `smoke_outcomes` because CAPTURE needs it too - it is
# what decides whether a job's next request is issued. These names are re-exported so the
# vocabulary stays where readers and reviewers already look for it.
PASS, FAIL, ADVISORY, FINDING = out.PASS, out.FAIL, out.ADVISORY, out.FINDING
INCONCLUSIVE = out.INCONCLUSIVE
CAPABILITY_PASS = out.CAPABILITY_PASS
CAPABILITY_PASS_BJ = out.CAPABILITY_PASS_BJ
CAPABILITY_INCONCLUSIVE = out.CAPABILITY_INCONCLUSIVE
CAPABILITY_FAIL = out.CAPABILITY_FAIL
JOB_FAILED = out.JOB_FAILED
JOB_INCONCLUSIVE_TRANSPORT = out.JOB_INCONCLUSIVE_TRANSPORT
JOB_INCONCLUSIVE_PAYLOAD = out.JOB_INCONCLUSIVE_PAYLOAD
JOB_INCONCLUSIVE_DECODE = out.JOB_INCONCLUSIVE_DECODE
JOB_NOT_SERVED = out.JOB_NOT_SERVED
JOB_INCONCLUSIVE_AUXILIARY = out.JOB_INCONCLUSIVE_AUXILIARY
JOB_CONTINUE = out.JOB_CONTINUE
OUTCOME_TABLE = out.OUTCOME_TABLE
lookup_outcome = out.lookup_outcome
transport_state_of = out.transport_state_of
_SEVERITY = out.SEVERITY

IDENTITY_SESSIONS = out.THRESHOLDS["identity_sessions"]
MIN_SEGMENT_SESSIONS = out.THRESHOLDS["min_segment_sessions"]
PRICE_TOL_REL = out.THRESHOLDS["price_tol_rel"]
VOLUME_TOL_REL = out.THRESHOLDS["volume_tol_rel"]
AMOUNT_TOL_REL = out.THRESHOLDS["amount_tol_rel"]
VOLUME_RATIO_STOCK = out.THRESHOLDS["volume_ratio_stock"]
VOLUME_RATIO_INDEX = out.THRESHOLDS["volume_ratio_index"]

#: The declared window, in the adapter's own `YYYYMMDD` form, passed explicitly to
#: `stock_zh_a_daily` so its client-side slice has real bounds (R2-C).
REPLAY_START = cap.WINDOW_START.replace("-", "")
REPLAY_END = cap.WINDOW_END.replace("-", "")


# ==================================================================== small utilities
def _sha256(data):
    return hashlib.sha256(data).hexdigest()


def _rel(actual, expected):
    return abs(actual - expected) / abs(expected) if expected else float("inf")


def check(cid, symbol, status, detail, measured=None, threshold=None, kind="required"):
    return {"id": cid, "symbol": symbol, "status": status, "detail": detail,
            "measured": measured, "threshold": threshold, "kind": kind}


def load_calendar(path):
    raw = Path(path).read_bytes()
    data = json.loads(raw.decode("utf-8"))
    values = [str(x["trade_date"] if isinstance(x, dict) else x) for x in data]
    sessions = sorted({(v[:4] + "-" + v[4:6] + "-" + v[6:8])
                       if len(v) == 8 and v.isdigit() else v for v in values})
    return sessions, _sha256(raw)


# ============================================================= B2: adapter-code facts
def adapter_basis_facts(source_path=None):
    """B2, derived by READING the installed adapter, not by assuming its arithmetic.

    The plan's earlier wording said qfq multiplies. It does not: the hfq branch
    multiplies by its factor and the qfq branch DIVIDES by its factor. Both are recorded
    from the installed text so the claim is checkable rather than remembered.
    """
    if source_path is None:
        from akshare.stock import stock_zh_a_sina

        source_path = Path(stock_zh_a_sina.__file__)
    text = Path(source_path).read_text(encoding="utf-8")
    facts = {
        "source": str(source_path),
        "source_sha256": _sha256(text.encode("utf-8")),
        "hfq_multiplies": '* temp_df["hfq_factor"]' in text.replace("\n", " "),
        "qfq_divides": '/ temp_df["qfq_factor"]' in text.replace("\n", " "),
        "raw_branch_has_no_factor": True,
    }
    marker = 'if adjust == "":'
    start = text.find(marker)
    end = text.find('if adjust == "hfq":', start if start >= 0 else 0)
    if start >= 0 and end > start:
        raw_branch = text[start:end]
        facts["raw_branch_has_no_factor"] = (
            "qfq_factor" not in raw_branch and "hfq_factor" not in raw_branch)
        facts["raw_branch_chars"] = len(raw_branch)
    facts["fetches_factor_only_when_adjusted"] = (
        "zh_sina_a_stock_qfq_url" in text and "zh_sina_a_stock_hfq_url" in text)
    return facts


# ================================================================ reference handling
def reference_rows(extract, manifest_symbol, instrument_class):
    """The frozen rows for one symbol, plus an explicit reference-quality verdict.

    A thin, zero-denominator or mixed-basis reference produces a stated reason and an
    INCONCLUSIVE check - never a repaired number, and never a change to production data.
    """
    rows = list(extract.get("rows", {}).get(manifest_symbol, []))
    expected_basis = "qfq" if instrument_class == "stock" else "none"
    #: The fixed ratios the identity checks apply are only meaningful against a reference
    #: whose recorded unit is the one they assume. `akshare_provider.py:111-112` stores
    #: stock volume in HANDS, which is why I3 expects 100; an index row carries no traded
    #: amount and its cache unit is `unknown`, which is acceptable only because its
    #: expected ratio is 1.0 (identity) and does not depend on the unit.
    accepted_units = {"stock": ("hand",), "benchmark": ("unknown", "share", "hand")}
    usable, reasons = [], []
    bases = sorted({r.get("adjustment_mode") for r in rows})
    units = sorted({r.get("volume_unit") for r in rows})
    sources = sorted({r.get("source") for r in rows})
    for row in rows:
        if row.get("adjustment_mode") != expected_basis:
            continue
        if row.get("close") in (None, 0) or float(row.get("close") or 0) <= 0:
            continue
        if row.get("volume") in (None,) or float(row.get("volume") or 0) <= 0:
            continue
        usable.append(row)
    if not rows:
        reasons.append("the frozen reference holds no rows for this symbol")
    if len(bases) > 1:
        reasons.append("the reference mixes adjustment bases %s; comparability is not "
                       "established" % bases)
    if len(units) > 1:
        reasons.append("the reference mixes volume units %s; a fixed ratio cannot be "
                       "interpreted against it" % units)
    elif units and units[0] not in accepted_units[instrument_class]:
        reasons.append("the reference volume unit %r is not one this check can interpret "
                       "for a %s (expected one of %s)"
                       % (units[0], instrument_class, list(accepted_units[instrument_class])))
    if not usable:
        reasons.append("no reference row has basis %r with a positive close and volume"
                       % expected_basis)
    quality = {"rows": len(rows), "usable_rows": len(usable), "bases": bases,
               "expected_basis": expected_basis, "units": units, "sources": sources,
               "accepted_units": list(accepted_units[instrument_class]),
               "reasons": reasons, "usable": not reasons}
    return usable, quality


def overlap_sessions(live_rows, ref_rows, limit=IDENTITY_SESSIONS):
    """The most recent sessions common to both series, oldest-first."""
    live = {r["date"]: r for r in live_rows}
    pairs = [(r["trade_date"], live[r["trade_date"]], r)
             for r in ref_rows if r["trade_date"] in live]
    pairs.sort(key=lambda item: item[0])
    return pairs[-limit:] if limit else pairs


def split_one_step(ratios, tol):
    """`(segment, step_index)` under the I2 one-step rule; `(None, None)` otherwise."""
    if all(abs(r - 1.0) <= tol for r in ratios):
        return list(range(len(ratios))), None
    steps = [i for i in range(1, len(ratios))
             if abs(ratios[i] - ratios[i - 1]) > tol]
    if len(steps) != 1:
        return None, None
    index = steps[0]
    segment = list(range(index, len(ratios)))
    if len(segment) < MIN_SEGMENT_SESSIONS:
        return None, None
    tail = [ratios[i] for i in segment]
    anchor = tail[0]
    if any(abs(r - anchor) > tol for r in tail):
        return None, None
    if abs(anchor - 1.0) > tol:
        return None, None
    return segment, index


# ============================================================ R1: the adapter replay
class _FakeResponse:
    def __init__(self, content, encoding):
        self.content = content
        self.encoding = encoding
        self.status_code = 200

    @property
    def text(self):
        return dec.bytes_to_text(self.content, self.encoding)


class _FakeRequests:
    """Serves ONLY the captured URLs. Any other URL is an immediate failure."""

    def __init__(self, bodies):
        self.bodies = bodies
        self.requested = []

    def get(self, url, params=None, **kwargs):
        full = url
        if params:
            full = url + "?" + "&".join("%s=%s" % kv for kv in sorted(params.items()))
        self.requested.append(full)
        if full not in self.bodies:
            raise AssertionError(
                "the adapter requested %s, which the smoke did not capture; a live "
                "fetch would have escaped the replay" % full)
        content, encoding = self.bodies[full]
        return _FakeResponse(content, encoding)


def _bounded_racer_module():
    """A `py_mini_racer` stand-in whose engine carries the decoder's own JS limits.

    The installed adapter builds its own `MiniRacer()` and calls it with no timeout, so
    the replay did not inherit P-B's bounds: a hostile or corrupt body could spin inside
    the vendor routine. Both adapter modules reference `py_mini_racer` as a module global,
    so swapping that global for this shim gives the installed code the same finite time
    and memory budget the pure decoder uses - without editing the vendor package.
    """
    import py_mini_racer

    class BoundedRacer(py_mini_racer.MiniRacer):
        def eval(self, code, *args, **kwargs):
            kwargs.setdefault("timeout_sec", dec.DECODE_TIMEOUT_SEC)
            kwargs.setdefault("max_memory", dec.DECODE_MAX_MEMORY)
            return super().eval(code, *args, **kwargs)

        def call(self, expr, *args, **kwargs):
            kwargs.setdefault("timeout_sec", dec.DECODE_TIMEOUT_SEC)
            kwargs.setdefault("max_memory", dec.DECODE_MAX_MEMORY)
            return super().call(expr, *args, **kwargs)

    class Shim:
        MiniRacer = BoundedRacer

        def __getattr__(self, name):
            return getattr(py_mini_racer, name)

    return Shim()


def adapter_replay(bodies, calls):
    """Call the installed adapter exactly as production would, on captured bytes.

    `calls` is `[(label, module_key, function_name, args)]`. Remote connections are
    blocked and both adapter modules' `requests` handle is swapped, so nothing can reach
    the vendor and an unexpected URL raises instead of being fetched. The guard is
    connection-level rather than a `socket.socket` block, because the adapter itself
    starts the JS engine, whose asyncio self-pipe is a local socket pair.
    """
    from akshare.stock import stock_zh_a_sina
    from akshare.index import index_stock_zh

    modules = {"stock": stock_zh_a_sina, "index": index_stock_zh}
    fake = _FakeRequests(bodies)
    bounded = _bounded_racer_module()
    saved = {name: mod.requests for name, mod in modules.items()}
    saved_racer = {name: getattr(mod, "py_mini_racer", None)
                   for name, mod in modules.items()}
    results = {}
    try:
        for name, mod in modules.items():
            mod.requests = fake
            if saved_racer[name] is not None:
                mod.py_mini_racer = bounded
        with cap.no_remote_connections("the adapter replay must not reach the network"):
            for label, module_key, func_name, args in calls:
                function = getattr(modules[module_key], func_name)
                frame = function(*args)
                dates = [str(d) for d in frame["date"].tolist()]
                results[label] = {
                    "rows": int(len(frame)),
                    "first_date": dates[0] if dates else None,
                    "last_date": dates[-1] if dates else None,
                    "dates": dates,
                    "columns": [str(c) for c in frame.columns],
                }
    finally:
        for name, mod in modules.items():
            mod.requests = saved[name]
            if saved_racer[name] is not None:
                mod.py_mini_racer = saved_racer[name]
    results["_requested_urls"] = list(fake.requested)
    return results


# ===================================================== B5: acceptance gates on evidence
def evidence_gates(manifest, reference_extract, calendar_sha):
    """Turn capture provenance from metadata into gates. Missing evidence never PASSes.

    Every one of these was previously recorded and then ignored: an explicitly
    invalidated capture, a reference hash that matched nothing, an unpinned calendar and
    a threshold contract that described the checks without being compared to them.
    """
    checks = []
    environment = manifest.get("environment") or {}

    # ---- EV0: a complete, valid capture envelope ---------------------------------
    problems = []
    if manifest.get("run_valid") is not True:
        problems.append("run_valid is %r; the capture did not certify itself"
                        % manifest.get("run_valid"))
    changes = manifest.get("invalidating_changes")
    if changes is None:
        problems.append("the manifest records no invalidating_changes list")
    elif changes:
        problems.append("protected inputs changed during the run: %s" % changes)
    if manifest.get("protected_after") is None:
        problems.append("no protected_after fingerprints were recorded")
    if manifest.get("deadline") is None:
        problems.append("no deadline provenance was recorded for the run")
    if not manifest.get("requests"):
        problems.append("the manifest carries no request records")
    indices = [r.get("index") for r in (manifest.get("requests") or [])
               if isinstance(r, dict)]
    duplicates = sorted({i for i in indices if indices.count(i) > 1})
    if duplicates:
        # A request has exactly one terminal record. Two records for one index (an
        # abandonment record beside a late publication) is corrupt evidence, never
        # something to collapse silently by "last one wins".
        problems.append("duplicate request records for index %s" % duplicates)
    checks.append(check("EV0", "run", PASS if not problems else FAIL,
                        "; ".join(problems) if problems else
                        "capture envelope complete and self-certified as valid",
                        {"run_valid": manifest.get("run_valid"),
                         "invalidating_changes": changes},
                        {"run_valid": True, "invalidating_changes": []}))

    # ---- EV3: the frozen reference is recomputed and bound to the capture ---------
    recomputed = cap.canonical_sha256({"rules": reference_extract.get("rules"),
                                       "rows": reference_extract.get("rows")})
    declared = reference_extract.get("content_sha256")
    bound = manifest.get("reference_extract_sha256")
    problems = []
    if declared != recomputed:
        problems.append("the extract's declared hash %s does not match its content (%s)"
                        % (str(declared)[:16], recomputed[:16]))
    if bound != recomputed:
        problems.append("the capture manifest binds reference hash %s, not this content"
                        % str(bound)[:16])
    checks.append(check("EV3", "run", PASS if not problems else FAIL,
                        "; ".join(problems) if problems else
                        "the frozen reference content hash was recomputed and matches "
                        "both its own declaration and the capture manifest",
                        {"recomputed": recomputed[:16], "declared": str(declared)[:16],
                         "bound_in_manifest": str(bound)[:16]},
                        {"all three": "equal"}), )

    # ---- EV4: approved pins ------------------------------------------------------
    pins = {"calendar_sha256": (calendar_sha, cap.CALENDAR_SHA256),
            "akshare_version": ((environment.get("adapter_constants") or {})
                                .get("akshare_version"), cap.AKSHARE_VERSION),
            "hk_js_decode_sha256": (environment.get("hk_js_decode_sha256"),
                                    dec.HK_JS_DECODE_SHA256)}
    problems = [name for name, (actual, expected) in pins.items() if actual != expected]
    missing = [name for name, (actual, _e) in pins.items() if actual is None]
    checks.append(check("EV4", "run",
                        PASS if not problems else (INCONCLUSIVE if problems == missing
                                                   else FAIL),
                        "every approved pin matches" if not problems else
                        "pin mismatch or missing provenance: %s" % problems,
                        {name: str(actual)[:16] for name, (actual, _e) in pins.items()},
                        {name: str(expected)[:16] for name, (_a, expected) in pins.items()}))

    # ---- EV5: the selection and threshold contract is verified, not described -----
    rules = reference_extract.get("rules") or {}
    expected_rules = {
        "symbols": [job["manifest_symbol"] for job in cap.JOBS],
        "window": [cap.WINDOW_START, cap.WINDOW_END],
        "basis_expected": out.BASIS_EXPECTED,
        "thresholds": out.THRESHOLDS,
    }
    mismatched = [key for key, want in expected_rules.items()
                  if rules.get(key) != want]
    checks.append(check("EV5", "run", PASS if not mismatched else FAIL,
                        "the frozen selection/threshold contract matches the constants "
                        "these checks apply" if not mismatched else
                        "the frozen contract disagrees with the applied checks on %s"
                        % mismatched,
                        {key: rules.get(key) for key in expected_rules},
                        expected_rules))
    return checks, recomputed


# ==================================================================== the check suite
def _replay_verdict(replay_info, fabricated, aux_missing, replay_error, *,
                    window=(cap.WINDOW_START, cap.WINDOW_END), label="adapter"):
    """`(status, detail)` for R1 - and a job that was NOT EVALUATED never reads as failed.

    R2-C. The old rule was `PASS if replay_info and not fabricated`, which passed on the
    mere absence of an exception, and its INCONCLUSIVE branch asserted the auxiliary body
    "was not captured" even when it had been captured and had failed to parse.

    R2-ABC-C2. It then trusted `first_date` METADATA as proof that dates came back, so
    `{rows: 1, first_date: "2023-01-03", last_date: None, dates: []}` passed. The actual
    returned sequence is now the evidence: it must be non-empty, agree with the row count
    and the first/last metadata, and - for the STOCK interface, which is given explicit
    dates - stay inside the declared window. `window=None` is the index interface, which
    takes no date arguments and returns the full served series; that is a different
    contract, not a laxer one, so the window is not imposed on it. This is defensive
    hardening; it is not a requirement that any security return a particular row count.
    """
    if replay_info:
        rows = replay_info.get("rows")
        first, last = replay_info.get("first_date"), replay_info.get("last_date")
        dates = list(replay_info.get("dates") or [])
        problems = []
        if fabricated:
            problems.append("%d dates absent from the raw decode" % len(fabricated))
        if not rows:
            problems.append("the adapter returned no rows")
        if not dates:
            problems.append("no actual date sequence was returned; a row count and "
                            "first/last metadata are not evidence of returned dates")
        else:
            if rows != len(dates):
                problems.append("the row count %r disagrees with the %d dates actually "
                                "returned" % (rows, len(dates)))
            if first != dates[0] or last != dates[-1]:
                problems.append("the first/last metadata %r..%r disagrees with the "
                                "returned sequence %s..%s"
                                % (first, last, dates[0], dates[-1]))
            if len(set(dates)) != len(dates):
                problems.append("the returned sequence repeats %d dates"
                                % (len(dates) - len(set(dates))))
            if dates != sorted(dates):
                problems.append("the returned dates are not in ascending order, so "
                                "first/last do not bound the sequence")
            if window:
                outside = sorted(d for d in dates
                                 if d < window[0] or d > window[1])
                if outside:
                    problems.append("%d returned dates fall outside the declared window "
                                    "%s..%s (e.g. %s)"
                                    % (len(outside), window[0], window[1], outside[:3]))
        scope = ("over the declared window %s..%s (requested as %s..%s)"
                 % (window[0], window[1], REPLAY_START, REPLAY_END) if window else
                 "(no date arguments; the index adapter returns the full served series)")
        detail = ("%s returned %s rows %s..%s %s" % (label, rows, first, last, scope))
        if problems:
            return FAIL, detail + "; " + "; ".join(problems)
        return PASS, detail
    if replay_error:
        return INCONCLUSIVE, ("the adapter replay did not complete for any job: %s"
                              % replay_error)
    if aux_missing:
        return INCONCLUSIVE, (
            "NOT EVALUATED: this job's auxiliary body was captured but could not be "
            "parsed, and the installed adapter fetches BOTH URLs, so it cannot be "
            "replayed from the retained bytes. This is an unevaluated job, not a failed "
            "one")
    return INCONCLUSIVE, "NOT EVALUATED: this job was not passed to the adapter replay"


def deadline_for(manifest, deadline=None, *, clock=None, label="checks"):
    """The deadline the checks run under, and where it comes from.

    An initial run hands in the SAME deadline capture used, so the budget is not silently
    reset between phases. When no live deadline is handed in, the one recorded in the
    capture manifest governs: its remaining budget is the remaining budget. That is what
    makes an already-exhausted run fail closed here instead of entering the installed
    adapter replay and blocking, which is what the reviewer reproduced.

    A separate offline replay passes its own fresh, explicitly bounded budget; it is a
    different run, and `replay()` says so.
    """
    if deadline is not None:
        return deadline, "handed in by the caller"
    snapshot = (manifest or {}).get("deadline")
    if not snapshot:
        return None, "the capture manifest records no deadline provenance"
    clock = clock or time.monotonic
    remaining = float(snapshot.get("remaining_sec", 0.0))
    if remaining <= 0:
        return "expired", ("the run deadline recorded by the capture is already spent "
                           "(%.1fs remaining)" % remaining)
    return (cap.Deadline(remaining, clock=clock,
                         grace_sec=float(snapshot.get("grace_sec",
                                                      cap.SHUTDOWN_GRACE_SEC)),
                         label=label),
            "derived from the capture manifest's recorded deadline")


def expected_transport_outcome(attempt):
    """The classification the unchanged M2a transport gives an attempt with this
    status/error (its own constants), so a manifest cannot carry a status that says one
    thing and a `transport_outcome` that says another."""
    status, error = attempt.get("status"), attempt.get("error")
    if status is not None:
        status = int(status)
        if status == 200:
            return "ok"
        if status in tp.STOP_STATUS:
            return "stop"
        if 300 <= status < 400:
            return "redirect"
        if status in tp.RETRYABLE_STATUS:
            return "retryable"
        return "failed"
    if error in ("TimeoutError", "ConnectionError"):
        return "transient"
    if error in ("RunAborted", "DeadlineExceeded"):
        return "stop"
    return "error"


def reconcile_attempts(manifest, records):
    """R3: bind every issued request to its actual attempt records, or fail closed.

    T3 previously checked an upper ceiling and stamped whatever attempts existed, so a
    manifest whose attempt array had been emptied still validated five successful
    requests. Now every issued request must have one or more attempt records; every
    attempt must name its request and its number; identity, URL, order, contiguity,
    source, terminal outcome and timestamps must agree; a skipped request must have
    none; every retry is accounted for; and the count the unchanged M2a transport kept
    must equal the count retained. Nothing is reconstructed from request records -
    missing attempt evidence is missing evidence.

    Returns `(problems, summary)`.
    """
    problems = []
    attempts = manifest.get("attempts")
    issued = {i for i, r in records.items()
              if r.get("outcome") in ("ok", "failed", "aborted")}
    skipped = {i for i, r in records.items() if r.get("outcome") == "skipped"}
    aborted_run = manifest.get("run_status") == "aborted"
    summary = {"attempts": 0, "requests_with_attempts": 0, "retries": 0,
               "min_gap_sec": None, "wire_starts": [],
               "transport_count": manifest.get("attempt_count_transport")}
    if not isinstance(attempts, list):
        return ["the manifest carries no attempt list"], summary
    summary["attempts"] = len(attempts)
    if issued and not attempts:
        problems.append("%d issued requests carry no attempt evidence at all"
                        % len(issued))
    if manifest.get("attempt_timestamps_complete") is not True:
        problems.append(
            "the capture did not record a wire-start timestamp for every attempt; "
            "pacing cannot be validated from this manifest")
    transport_count = manifest.get("attempt_count_transport")
    unfinished_last = bool(attempts) and isinstance(attempts[-1], dict) and \
        attempts[-1].get("finished_at_monotonic") is None
    if transport_count is None:
        problems.append("the capture recorded no transport attempt count to reconcile "
                        "against")
    elif transport_count != len(attempts) - (1 if unfinished_last else 0):
        # An in-flight attempt is by construction not yet counted by the transport.
        problems.append("the transport counted %s attempts but %d attempt records are "
                        "retained (truncated or padded evidence)"
                        % (transport_count, len(attempts)))
    if len(attempts) > cap.CEILING:
        problems.append("%d attempts exceed the ceiling of %d"
                        % (len(attempts), cap.CEILING))

    required = ("request_index", "attempt_no", "url", "source",
                "started_at_monotonic", "started_at_utc")
    by_request, closed, last_index, previous, stamps = {}, set(), None, None, []
    for position, attempt in enumerate(attempts):
        if not isinstance(attempt, dict):
            problems.append("attempt %d is not a record" % position)
            continue
        missing = [f for f in required if attempt.get(f) is None]
        if missing:
            problems.append("attempt %d lacks %s" % (position, missing))
        index = attempt.get("request_index")
        if index not in records:
            problems.append("attempt %d names request %r, which was not planned"
                            % (position, index))
        else:
            if attempt.get("url") != records[index]["requested_url"]:
                problems.append("attempt %d URL differs from request %d's requested URL"
                                % (position, index))
            if index in skipped and not attempt.get("refused_before_wire"):
                # A call refused before it reached the wire is legitimately bound to a
                # request the owner had already closed; anything else is not.
                problems.append("attempt %d belongs to request %d, which is recorded as "
                                "skipped" % (position, index))
        if attempt.get("source") != cap.SOURCE_KEY:
            problems.append("attempt %d does not carry the source key %r"
                            % (position, cap.SOURCE_KEY))
        if last_index is not None and index != last_index:
            closed.add(last_index)
            if index in closed:
                problems.append("attempts for request %r resume at position %d after "
                                "another request's attempts (duplicated or reordered "
                                "evidence)" % (index, position))
            if isinstance(index, int) and isinstance(last_index, int) and index < last_index:
                problems.append("attempts are out of request order at position %d"
                                % position)
        last_index = index
        sequence = by_request.setdefault(index, [])
        if attempt.get("attempt_no") != len(sequence) + 1:
            problems.append("attempt numbering for request %r is not contiguous at "
                            "position %d (got %r, expected %d)"
                            % (index, position, attempt.get("attempt_no"),
                               len(sequence) + 1))
        sequence.append(attempt)
        if len(sequence) > tp.MAX_ATTEMPTS_PER_JOB:
            problems.append("request %r has %d attempts, more than the %d allowed"
                            % (index, len(sequence), tp.MAX_ATTEMPTS_PER_JOB))
        stamp = attempt.get("started_at_monotonic")
        if stamp is not None:
            stamps.append(stamp)
            if previous is not None and stamp <= previous:
                problems.append("attempt %d does not start after the previous attempt"
                                % position)
            previous = stamp
        finished = attempt.get("finished_at_monotonic")
        if finished is None:
            if position != len(attempts) - 1 or not aborted_run:
                problems.append("attempt %d has no finish record and is not the final "
                                "attempt of an aborted run" % position)
            elif not (attempt.get("status") is None and attempt.get("error") is None
                      and attempt.get("transport_outcome") is None):
                problems.append("attempt %d is unfinished but carries a result" % position)
        elif stamp is not None and finished < stamp:
            problems.append("attempt %d finishes before it starts" % position)
        elif attempt.get("transport_outcome") is None:
            problems.append("attempt %d carries no transport classification" % position)
        elif attempt.get("transport_outcome") != expected_transport_outcome(attempt):
            problems.append("attempt %d is classified %r but its status/error (%r/%r) "
                            "imply %r" % (position, attempt.get("transport_outcome"),
                                          attempt.get("status"), attempt.get("error"),
                                          expected_transport_outcome(attempt)))

    gaps = [round(b - a, 3) for a, b in zip(stamps, stamps[1:])]
    tight = [g for g in gaps if g < cap.MIN_INTERVAL]
    if tight:
        problems.append("pacing violated on %d consecutive attempt pairs (min %.3fs)"
                        % (len(tight), min(gaps)))
    summary["min_gap_sec"] = min(gaps) if gaps else None
    summary["wire_starts"] = stamps

    for index in sorted(issued):
        record = records[index]
        sequence = by_request.get(index, [])
        outcome = record.get("outcome")
        if not sequence:
            if outcome == "aborted" and aborted_run:
                continue                      # aborted before its first attempt
            problems.append("request %d is recorded %s but has no attempt record"
                            % (index, outcome))
            continue
        summary["requests_with_attempts"] += 1
        summary["retries"] += len(sequence) - 1
        declared = record.get("attempt_count")
        positions = record.get("attempt_positions")
        actual = [p for p, a in enumerate(attempts)
                  if isinstance(a, dict) and a.get("request_index") == index]
        if declared is None or positions is None:
            problems.append("request %d carries no attempt binding (attempt_count / "
                            "attempt_positions)" % index)
        elif declared != len(sequence) or list(positions) != actual:
            problems.append("request %d declares attempt binding %s/%s but the attempt "
                            "list binds %d attempts at %s"
                            % (index, declared, list(positions), len(sequence), actual))
        if sequence[-1].get("finished_at_monotonic") is None and outcome != "aborted":
            problems.append("request %d is recorded %s while its final attempt is still "
                            "in flight" % (index, outcome))
        for earlier in sequence[:-1]:
            if earlier.get("transport_outcome") not in ("transient", "retryable"):
                problems.append("request %d was retried after a non-retryable attempt "
                                "(%r)" % (index, earlier.get("transport_outcome")))
                break
        last = sequence[-1]
        last_outcome = last.get("transport_outcome")
        if outcome == "ok":
            if last.get("status") != 200 or last_outcome != "ok":
                problems.append("request %d is recorded ok but its final attempt is "
                                "%r/%r" % (index, last.get("status"), last_outcome))
        elif outcome == "failed":
            if last_outcome == "ok":
                problems.append("request %d is recorded failed but its final attempt "
                                "succeeded" % index)
            elif (last_outcome in ("transient", "retryable")
                  and len(sequence) < tp.MAX_ATTEMPTS_PER_JOB):
                problems.append("request %d gave up after %d retryable attempts without "
                                "exhausting the %d allowed"
                                % (index, len(sequence), tp.MAX_ATTEMPTS_PER_JOB))
            if record.get("status") != last.get("status"):
                problems.append("request %d records status %r but its final attempt saw "
                                "%r" % (index, record.get("status"), last.get("status")))
            if record.get("transport_outcome") != last_outcome:
                problems.append("request %d records transport_outcome %r but its final "
                                "attempt is %r" % (index, record.get("transport_outcome"),
                                                   last_outcome))
            if bool(record.get("retryable")) != (last_outcome in ("transient", "retryable")):
                problems.append("request %d records retryable=%r but its final attempt "
                                "is %r" % (index, record.get("retryable"), last_outcome))
            if (record.get("failure_kind") == "tls") != (last.get("error") == "TlsFailure"):
                problems.append("request %d records failure_kind %r but its final attempt "
                                "error is %r" % (index, record.get("failure_kind"),
                                                 last.get("error")))
        elif outcome == "aborted":
            explained = (last_outcome == "stop"
                         or last.get("error") in ("DeadlineExceeded", "RunAborted")
                         or (record.get("abandoned") is True and aborted_run))
            if not explained:
                problems.append("request %d is recorded aborted but its final attempt is "
                                "%r/%r" % (index, last.get("status"), last_outcome))
    return problems, summary


def run_checks(*, manifest, raw_dir, reference_extract, calendar_path=cap.CALENDAR,
               routine=None, routine_sha256=dec.HK_JS_DECODE_SHA256, racer_factory=None,
               replay_fn=adapter_replay, deadline=None, clock=None):
    """Every Section 6 check, from retained evidence only, under an active deadline.

    Returns `{"deterministic": {...}, "run_meta": {...}}`. Only the deterministic block
    is hashed and compared on replay; run timestamps and durations live in `run_meta` so
    they cannot make an unchanged result look changed.

    Raises `cap.DeadlineExceeded` rather than continuing past the run's budget. Decoding
    and the installed-adapter replay - the two places that can block - are supervised, so
    the bound holds on the ACTUAL call path and not only in a helper.
    """
    raw_dir = Path(raw_dir)
    sessions, calendar_sha = load_calendar(calendar_path)
    session_set = set(sessions)
    checks = []
    jobs = {j["job"]: dict(j) for j in cap.JOBS}
    decoded = {}
    outcomes = {}
    records = {}
    for record in manifest["requests"]:
        # First record wins so an owner abandonment record is never hidden by a later
        # publication; EV0 fails the run on the duplicate regardless.
        records.setdefault(record["index"], record)

    deadline, deadline_source = deadline_for(manifest, deadline, clock=clock)
    if deadline == "expired":
        raise cap.DeadlineExceeded(
            "refusing to decode, check or replay: %s. Retained evidence is untouched; a "
            "later offline replay may run under its own explicit budget."
            % deadline_source)
    if deadline is None:
        # No recorded budget is missing provenance, not permission to run unbounded.
        deadline = cap.Deadline(cap.REPLAY_BUDGET_SEC, clock=clock or time.monotonic,
                                label="checks (no recorded budget)")
    deadline.check("checks-start")

    # B5: capture provenance is a GATE, not metadata. These run first so a missing or
    # explicitly invalidated envelope can never be rescued by later PASSes.
    gate_checks, reference_content_sha = evidence_gates(manifest, reference_extract,
                                                        calendar_sha)
    checks.extend(gate_checks)

    if routine is None:
        from akshare.stock.cons import hk_js_decode as routine
    if racer_factory is None:
        racer_factory = dec.default_racer_factory

    # ------------------------------------------------------- decode every captured body
    payload_state = {}
    for index in sorted(records):
        record = records[index]
        if record.get("outcome") != "ok":
            payload_state[index] = "not_applicable"
            continue
        blob = raw_dir / record["raw_file"]
        content = blob.read_bytes()
        if not content:
            # An empty 200 is its own payload state; it must not be reported as a
            # decoder defect, because the two mean different things (S2).
            payload_state[index] = "empty"
            continue
        if _sha256(content) != record["body_sha256"]:
            payload_state[index] = "undecodable"
            checks.append(check("EV1", record["symbol"], FAIL,
                                "the retained body does not match its recorded hash",
                                _sha256(content)[:16], record["body_sha256"][:16]))
            continue
        try:
            text = dec.bytes_to_text(content, record.get("encoding"))
        except dec.DecodeError as exc:
            payload_state[index] = "undecodable"
            checks.append(check("EV2", record["symbol"], FAIL,
                                "bytes-to-text failed: %s" % exc))
            continue
        # Minor clarification: compare the bytes-to-TEXT step with the captured
        # `response.text`, not the decoder's record output with a string.
        text_ok = dec.sha256_text(text) == record.get("text_sha256")
        checks.append(check(
            "EV2", record["symbol"], PASS if text_ok else FAIL,
            "P-B's bytes-to-text reproduces the captured response.text"
            if text_ok else "P-B's strict decode differs from the captured response.text "
                            "(requests used errors='replace')",
            dec.sha256_text(text)[:16], (record.get("text_sha256") or "")[:16]))
        if not text_ok:
            payload_state[index] = "undecodable"
            continue

        # The SAME classifier capture used, supervised so a body that will not decode
        # cannot run past the run's budget on the actual check path.
        deadline.check("decode-%02d" % index)
        state, payload, reason = cap.supervise(
            lambda: out.classify_payload(
                content, record["kind"], encoding=record.get("encoding"),
                routine=routine, routine_sha256=routine_sha256,
                racer_factory=racer_factory, expected_symbol=record["symbol"],
                instrument_class=jobs[record["job"]]["instrument_class"]),
            deadline=deadline, poll_sec=cap.SUPERVISE_POLL_SEC,
            name="m2b-check-decode-%02d" % index)
        payload_state[index] = state
        if payload is not None:
            decoded[index] = payload
        if state in ("undecodable", "no_rows"):
            checks.append(check("S2", record["symbol"], FAIL,
                                "the pinned routine could not decode this body: %s"
                                % reason))
        # Capture recorded its own classification of the same bytes. If the two disagree
        # the evidence is not self-consistent, which is a finding in itself.
        recorded = record.get("payload_state")
        if recorded is not None and recorded != state:
            checks.append(check("EV6", record["symbol"], FAIL,
                                "capture classified this body as %r; the retained bytes "
                                "classify as %r" % (recorded, state), state, recorded))

    # ---------------------------------------------- the outcome table drives everything
    job_results = {}
    job_notes = {}
    for job_name in jobs:
        job_records = [records[i] for i in sorted(records) if records[i]["job"] == job_name]
        rows = []
        skip_from = None
        by_kind = {}
        for record in job_records:
            index = record["index"]
            state = transport_state_of(record)
            row = lookup_outcome(state, payload_state.get(index, "not_applicable"))
            entry = {"index": index, "kind": record["kind"],
                     "transport_state": state,
                     "payload_state": payload_state.get(index, "not_applicable"),
                     **{k: row[k] for k in ("request_result", "job_result",
                                            "evidence_class", "skip_remaining",
                                            "aborts_run", "note")}}
            rows.append(entry)
            by_kind[record["kind"]] = (record, entry)
            if row["skip_remaining"] and skip_from is None:
                skip_from = index
        # R4: the job result is REQUEST-KIND specific. Only the KLC history request can
        # yield the explicit-absence result; a failed or absent auxiliary request is
        # inconclusive auxiliary evidence, and the history body already received is
        # still checked. A request never issued without a trigger is a contradiction.
        worst, note = out.aggregate_job(by_kind.get("klc"),
                                        by_kind.get("outstanding_share"))
        if worst == JOB_FAILED:
            for row in rows:
                if (records[row["index"]].get("outcome") != "ok"
                        and row["job_result"] == JOB_CONTINUE):
                    row["job_result"] = JOB_FAILED
                    row["note"] = ("a request of this job was not issued and no earlier "
                                   "outcome triggered a skip")
        outcomes[job_name] = {"requests": rows, "job_result": worst,
                              "skip_triggered_at": skip_from, "aggregation": note}
        job_results[job_name] = worst
        job_notes[job_name] = note

    # T3 request-count consistency: skipping is legal only downstream of a skip trigger.
    count_problems = []
    issued = [r for r in records.values() if r.get("outcome") in ("ok", "failed", "aborted")]
    skipped = [r for r in records.values() if r.get("outcome") == "skipped"]
    if len(records) != 5:
        count_problems.append("expected 5 planned requests, found %d" % len(records))
    # A job-local skip needs an upstream trigger IN THAT JOB. A run-global skip is
    # explained by the run abort itself and needs no such trigger - the two were
    # previously conflated, so an aborted run reported its own untouched jobs as
    # contradictions.
    for job_name, info in outcomes.items():
        trigger = info["skip_triggered_at"]
        for row in info["requests"]:
            record = records[row["index"]]
            if record.get("outcome") == "skipped":
                scope = record.get("skip_scope")
                if scope == out.SKIP_RUN_GLOBAL:
                    if manifest.get("run_status") != "aborted":
                        count_problems.append(
                            "request %d claims a run-global skip but the run is %r"
                            % (row["index"], manifest.get("run_status")))
                elif scope in (out.SKIP_JOB_LOCAL, None):
                    if trigger is None or row["index"] <= trigger:
                        count_problems.append(
                            "request %d was skipped with no earlier skip trigger in job %s"
                            % (row["index"], job_name))
                else:
                    count_problems.append("request %d carries an unknown skip scope %r"
                                          % (row["index"], scope))
            elif trigger is not None and row["index"] > trigger:
                count_problems.append(
                    "request %d was issued after the skip trigger in job %s"
                    % (row["index"], job_name))

    # ------------------------------------- R3: attempts reconciled with the requests
    # Pacing is measured on the ACTUAL post-pacing wire start of every attempt, retries
    # included, and every issued request must be bound to its attempt records: an empty,
    # truncated, duplicated or inconsistent attempt list fails, it is never rebuilt.
    attempt_problems, attempt_summary = reconcile_attempts(manifest, records)
    count_problems.extend(attempt_problems)
    checks.append(check("T3", "run", PASS if not count_problems else FAIL,
                        "; ".join(count_problems) if count_problems else
                        "attempts within the ceiling, source key uniform, pacing "
                        "respected on actual wire starts (retries included), every "
                        "issued request bound to its attempt records, request count "
                        "consistent with the outcome table",
                        dict(attempt_summary, issued=len(issued), skipped=len(skipped)),
                        {"ceiling": cap.CEILING, "min_interval_sec": cap.MIN_INTERVAL,
                         "max_attempts_per_request": tp.MAX_ATTEMPTS_PER_JOB}))

    for record in issued:
        symbol = record["symbol"]
        if record.get("outcome") != "ok":
            continue
        served_ok = record.get("served_url") == record["requested_url"]
        checks.append(check("T1", symbol, PASS if record["status"] == 200 and served_ok
                            else FAIL,
                            "status %s; served URL %s requested URL"
                            % (record["status"], "equals" if served_ok else "DIFFERS FROM"),
                            record["status"], 200))
        checks.append(check("T2", symbol, PASS if payload_state[record["index"]] not in
                            ("empty", "markup") else FAIL,
                            "payload state %r" % payload_state[record["index"]],
                            payload_state[record["index"]], "non-empty, not markup"))

    # ----------------------------------------------------------- S1: expected URL set
    expected = {item["index"]: item for item in
                cap.expected_requests(manifest["environment"].get("adapter_constants"))}
    for job_name in jobs:
        want = {expected[i]["url"] for i in expected if expected[i]["job"] == job_name}
        got = {records[i]["requested_url"] for i in records if records[i]["job"] == job_name}
        checks.append(check("S1", job_name, PASS if want == got else FAIL,
                            "the planned URL set matches the installed adapter constants"
                            if want == got else "URL set mismatch: missing=%s extra=%s"
                            % (sorted(want - got), sorted(got - want)),
                            sorted(got), sorted(want)))

    # --------------------------------------------------------------- per-symbol checks
    bodies = {}
    for index, record in records.items():
        if record.get("outcome") == "ok":
            blob = (raw_dir / record["raw_file"]).read_bytes()
            bodies[record["requested_url"]] = (blob, record.get("encoding"))

    basis_facts = adapter_basis_facts()
    checks.append(check(
        "B2", "run",
        PASS if (basis_facts["hfq_multiplies"] and basis_facts["qfq_divides"]
                 and basis_facts["raw_branch_has_no_factor"]) else FAIL,
        "code-derived: the hfq branch MULTIPLIES by its factor, the qfq branch DIVIDES "
        "by its factor, and the adjust=\"\" branch applies neither",
        basis_facts, {"hfq_multiplies": True, "qfq_divides": True,
                      "raw_branch_has_no_factor": True}))

    factor_urls = [r["requested_url"] for r in records.values()
                   if "qfq.js" in r["requested_url"] or "hfq.js" in r["requested_url"]]
    checks.append(check("B1", "run", PASS if not factor_urls else FAIL,
                        "no factor endpoint was requested" if not factor_urls
                        else "factor endpoints requested: %s" % factor_urls,
                        factor_urls, []))

    replay = {}
    replay_error = None
    if bodies:
        calls = []
        for job in cap.JOBS:
            job_rows = [records[i] for i in sorted(records) if records[i]["job"] == job["job"]]
            if any(r.get("outcome") != "ok" for r in job_rows):
                continue
            if job["instrument_class"] == "stock":
                # R2-C: explicit window dates. Empty strings reached the adapter's
                # `temp_df[start:end]` slice on a DatetimeIndex and raised TypeError, so
                # the replay never ran and every per-symbol R1 read INCONCLUSIVE.
                calls.append((job["job"], "stock", "stock_zh_a_daily",
                              (job["adapter_symbol"], REPLAY_START, REPLAY_END, "")))
            else:
                calls.append((job["job"], "index", "stock_zh_index_daily",
                              (job["adapter_symbol"],)))
        if calls:
            try:
                deadline.check("adapter-replay")
                replay = cap.supervise(
                    lambda: replay_fn(bodies, calls), deadline=deadline,
                    poll_sec=cap.SUPERVISE_POLL_SEC, name="m2b-adapter-replay")
            except Exception as exc:                  # noqa: BLE001
                replay = {"error": "%s: %s" % (type(exc).__name__, exc)}
                replay_error = replay["error"]
                checks.append(check("R1", "run", FAIL,
                                    "the adapter replay raised: %s" % replay["error"]))

    def request_summary(job_name):
        """Per request kind: what the transport and the payload said. Recorded on C2 so
        a BJ classification always shows WHICH request produced it (R4)."""
        summary = {}
        for row in outcomes[job_name]["requests"]:
            record = records[row["index"]]
            summary[row["kind"]] = {"index": row["index"], "outcome": record.get("outcome"),
                                    "status": record.get("status"),
                                    "transport_state": row["transport_state"],
                                    "payload_state": row["payload_state"],
                                    "request_result": row["request_result"]}
        return summary

    for job in cap.JOBS:
        deadline.check("checks-%s" % job["job"])
        name = job["job"]
        klass = job["instrument_class"]
        result = job_results[name]
        aux_missing = result == JOB_INCONCLUSIVE_AUXILIARY
        if aux_missing:
            # R4: history was served and decoded; the auxiliary endpoint was not. The
            # history checks below still run, so invalid history cannot hide behind a
            # missing share series, and this job can never become an absence finding.
            checks.append(check("JOBaux", name, INCONCLUSIVE, job_notes[name],
                                request_summary(name), JOB_CONTINUE))
        elif result != JOB_CONTINUE:
            if result == JOB_NOT_SERVED and name == "bj920000":
                status, kind = FINDING, "finding"
            elif result == JOB_NOT_SERVED:
                status, kind = FAIL, "required"
            elif result.startswith("INCONCLUSIVE"):
                status, kind = INCONCLUSIVE, "required"
            else:
                status, kind = FAIL, "required"
            checks.append(check("JOB", name, status,
                                "outcome table result %s (%s); per-symbol checks are not "
                                "reached" % (result, job_notes[name]), result,
                                JOB_CONTINUE, kind=kind))
            if name == "bj920000":
                classification = (
                    "vendor_explicit_absence_at_path" if result == JOB_NOT_SERVED
                    else "inconclusive")
                checks.append(check(
                    "C2", name, FINDING,
                    "BJ outcome %r from the KLC history request; the CAUSE (code mapping "
                    "or otherwise) is NOT established by this observation"
                    % classification,
                    {"classification": classification, "cause": "not established",
                     "job_result": result, "decided_by": "klc",
                     "auxiliary_evidence": "absent",
                     **{"%s_request" % k: v for k, v in request_summary(name).items()}},
                    None, kind="finding"))
            continue

        klc_index = next(i for i in sorted(records)
                         if records[i]["job"] == name and records[i]["kind"] == "klc")
        payload = decoded[klc_index]
        rows = payload["rows"]
        symbol = job["manifest_symbol"]

        # D1 / D2 ------------------------------------------------------------------
        # R2-B: the COMPLETE variable name is matched against the expected exchange and
        # symbol. Collecting every digit made `KLC_K2_sh600011` yield `2600011` and fail
        # a body it had just decoded; only the index prefix `KLC_KL_` escaped it.
        var_ok, var_reason = dec.check_js_variable(
            payload["js_variable"], "klc", klass, job["adapter_symbol"])
        expected_var = dec.expected_js_variable("klc", klass, job["adapter_symbol"])
        checks.append(check("D1", name, PASS if rows and var_ok else FAIL,
                            "%s; %d rows, decoder branch %s (%d)"
                            % (var_reason, len(rows), payload["branch"],
                               payload["branch_code"]),
                            {"js_variable": payload["js_variable"],
                             "expected_js_variable": expected_var,
                             "branch": payload["branch"], "rows": len(rows)},
                            {"js_variable": expected_var, "rows": ">= 1"}))
        report = dec.key_report(rows, klass)
        d2_ok = not report["missing"]
        checks.append(check("D2", name, PASS if d2_ok else FAIL,
                            "keys present" if d2_ok else "missing required keys %s"
                            % report["missing"], report,
                            list(dec.STOCK_REQUIRED_KEYS if klass == "stock"
                                 else dec.INDEX_REQUIRED_KEYS)))

        # D3 -----------------------------------------------------------------------
        in_window = [r for r in rows if cap.WINDOW_START <= r["date"] <= cap.WINDOW_END]
        off_calendar = sorted({r["date"] for r in in_window if r["date"] not in session_set})
        after_window = sorted({r["date"] for r in rows if r["date"] > cap.WINDOW_END})
        checks.append(check("D3", name, PASS if not off_calendar else FAIL,
                            "all in-window dates are on the pinned calendar"
                            if not off_calendar else
                            "%d in-window dates are off-calendar" % len(off_calendar),
                            {"off_calendar": off_calendar[:10],
                             "after_window": after_window[:10],
                             "in_window_rows": len(in_window)}, {"off_calendar": 0}))

        # D4 -----------------------------------------------------------------------
        research = [r for r in rows if cap.RESEARCH_START <= r["date"] <= cap.RESEARCH_END]
        broken = [r["date"] for r in research
                  if float(r.get("volume") or 0) > 0
                  and not (float(r["low"]) <= min(float(r["open"]), float(r["close"]))
                           and max(float(r["open"]), float(r["close"])) <= float(r["high"]))]
        checks.append(check("D4", name, PASS if not broken else FAIL,
                            "OHLC ordering holds on every traded research row"
                            if not broken else "%d research rows break OHLC ordering"
                            % len(broken), broken[:10], []))

        # D5 + U4 (date-aligned) ---------------------------------------------------
        share_series = []
        if klass == "stock":
            share_index = next((i for i in sorted(records)
                                if records[i]["job"] == name
                                and records[i]["kind"] == "outstanding_share"), None)
            if aux_missing or share_index not in decoded:
                aux = request_summary(name).get("outstanding_share")
                checks.append(check(
                    "D5", name, INCONCLUSIVE,
                    "no outstanding-share series: the auxiliary request is %s/%s "
                    "(status %s). This is missing AUXILIARY evidence, not history "
                    "evidence" % ((aux or {}).get("transport_state"),
                                  (aux or {}).get("payload_state"),
                                  (aux or {}).get("status")),
                    {"auxiliary_request": aux}, {"entries": ">= 1"}))
                checks.append(check("U4", name, ADVISORY,
                                    "not computable without the outstanding-share series",
                                    None, None, kind="advisory"))
            else:
                share_series = decoded[share_index]["share_series"]
                checks.append(check("D5", name, PASS if share_series else FAIL,
                                    "%d [date, outstanding_share_wan] entries; never "
                                    "labelled amount" % len(share_series),
                                    {"entries": len(share_series),
                                     "label": "outstanding_share_wan"},
                                    {"entries": ">= 1"}))
                # R2-A: the share series is a STEP function of share-count changes, so
                # the value in force on a trading day is the LATEST observation at or
                # before it - which is what the installed adapter's ffill does. Exact
                # date matching reported "0 common dates" for SH600011, whose last
                # observation (2019-10-15) precedes the window entirely. This carries
                # forward and never backfills.
                # R2-ABC-C1: an explicit zero in force yields NO denominator - an older
                # positive count is not restored across it - so there are two distinct
                # reasons for having none, and they are counted apart: no observation
                # exists yet, versus an explicit invalid observation is in force and has
                # not been superseded by a later valid one.
                aligned, ages = [], []
                before_series, under_invalid = 0, 0
                for r in research:
                    if r.get("volume") is None:
                        continue
                    asof = dec.outstanding_share_as_of(share_series, r["date"])
                    if asof is None:
                        state = dec.share_state_as_of(share_series, r["date"])
                        if state is None:
                            before_series += 1
                        else:
                            under_invalid += 1
                        continue
                    aligned.append((r["date"], float(r["volume"]),
                                    asof["outstanding_share_wan"]))
                    ages.append(dec._age_days(asof, r["date"]))
                unmatched = before_series + under_invalid
                invalid_spans = dec.invalid_denominator_intervals(share_series)
                exceeded = [d for d, vol, wan in aligned if vol > wan * 10000.0]
                checks.append(check(
                    "U4", name, ADVISORY,
                    "as-of turnover check on %d research rows (%d had no applicable "
                    "share observation: %d before the series begins, %d while an "
                    "explicit invalid observation was in force); %d exceed 100%%. "
                    "Denominator age: %s"
                    % (len(aligned), unmatched, before_series, under_invalid,
                       len(exceeded),
                       ("median %d days, max %d days - a value carried forward this long "
                        "is weak evidence, not a fresh measurement"
                        % (sorted(ages)[len(ages) // 2], max(ages))) if ages
                       else "n/a"),
                    {"aligned_rows": len(aligned),
                     "rows_without_applicable_share": unmatched,
                     "rows_before_the_first_observation": before_series,
                     "rows_under_an_invalid_observation": under_invalid,
                     "invalid_denominator_intervals": invalid_spans,
                     "denominator_age_days_median": (sorted(ages)[len(ages) // 2]
                                                     if ages else None),
                     "denominator_age_days_max": max(ages) if ages else None,
                     "exceeding": exceeded[:5]},
                    {"volume <= outstanding_share_wan * 10000": True}, kind="advisory"))

            # U1 -------------------------------------------------------------------
            zero = [r["date"] for r in research
                    if not (float(r.get("volume") or 0) > 0
                            and float(r.get("amount") or 0) > 0)]
            checks.append(check("U1", name, PASS if not zero else FAIL,
                                "every research row has positive volume and amount"
                                if not zero else "%d research rows are zero" % len(zero),
                                zero[:10], []))

            # U2 -------------------------------------------------------------------
            unit_window, ev_window = prov.derive_unit(in_window)
            unit_all, ev_all = prov.derive_unit(rows)
            checks.append(check(
                "U2", name, PASS if unit_window in ("share", "hand") else FAIL,
                "windowed unit %r (%s)" % (unit_window, ev_window.get("unit_reason")),
                {"windowed": unit_window, "windowed_evidence": ev_window,
                 "all_rows": unit_all, "all_rows_evidence": ev_all,
                 "diverges": unit_window != unit_all},
                {"unit": "share or hand"}))

        # B3 (advisory) --------------------------------------------------------------
        with_prev = [r for r in rows if "prevclose" in r]
        mismatches = []
        for previous, current in zip(rows, rows[1:]):
            if "prevclose" in current and previous.get("close") is not None:
                if _rel(float(current["prevclose"]), float(previous["close"])) > 1e-6:
                    mismatches.append(current["date"])
        checks.append(check("B3", name, ADVISORY,
                            "%d rows carry prevclose; %d differ from the previous close "
                            "(candidate corporate-action markers, never basis evidence)"
                            % (len(with_prev), len(mismatches)),
                            {"rows_with_prevclose": len(with_prev),
                             "mismatch_dates": mismatches[:10]}, None, kind="advisory"))

        # I2 / I3 / U3 against the FROZEN reference ---------------------------------
        ref, quality = reference_rows(reference_extract, symbol, klass)
        pairs = overlap_sessions(rows, ref)
        if not quality["usable"] or len(pairs) < MIN_SEGMENT_SESSIONS:
            reason = ("; ".join(quality["reasons"]) or
                      "only %d overlapping sessions, fewer than the %d needed"
                      % (len(pairs), MIN_SEGMENT_SESSIONS))
            for cid in ("I2", "I3", "U3") if klass == "stock" else ("I2", "I3"):
                checks.append(check(cid, name, INCONCLUSIVE,
                                    "reference quality: %s" % reason,
                                    {"overlap": len(pairs), "quality": quality},
                                    {"overlap": ">= %d" % MIN_SEGMENT_SESSIONS}))
        else:
            ratios, tol_each = [], []
            for date, live, local in pairs:
                close_local = float(local["close"])
                ratios.append(float(live["close"]) / close_local)
                tol_each.append(max(PRICE_TOL_REL, 0.01 / close_local))
            tol = max(tol_each)
            segment, step = split_one_step(ratios, tol)
            i2_ok = segment is not None
            checks.append(check(
                "I2", name, PASS if i2_ok else FAIL,
                "close ratio within tolerance on %d sessions%s"
                % (len(segment) if segment else 0,
                   "" if step is None else " after one step at %s" % pairs[step][0])
                if i2_ok else "close ratios are neither flat nor a single step",
                {"ratios": [round(r, 6) for r in ratios],
                 "step_date": pairs[step][0] if step is not None else None,
                 "sources": sorted({p[2].get("source") for p in pairs})},
                {"tolerance": round(tol, 6)}))

            use = segment if segment else list(range(len(pairs)))
            want_ratio = VOLUME_RATIO_STOCK if klass == "stock" else VOLUME_RATIO_INDEX
            vol_ratios = [float(pairs[i][1]["volume"]) / float(pairs[i][2]["volume"])
                          for i in use if float(pairs[i][2].get("volume") or 0) > 0]
            i3_ok = bool(vol_ratios) and all(
                _rel(r, want_ratio) <= VOLUME_TOL_REL for r in vol_ratios)
            checks.append(check("I3", name, PASS if i3_ok else FAIL,
                                "volume ratio ~ %g on %d sessions"
                                % (want_ratio, len(vol_ratios)),
                                [round(r, 4) for r in vol_ratios],
                                {"ratio": want_ratio, "tolerance": VOLUME_TOL_REL}))

            if klass == "stock":
                amount_pairs = [(pairs[i][1], pairs[i][2]) for i in use
                                if pairs[i][2].get("amount") is not None
                                and float(pairs[i][2]["amount"]) > 0
                                and pairs[i][1].get("amount") is not None]
                if not amount_pairs:
                    checks.append(check("U3", name, INCONCLUSIVE,
                                        "no session in the compared segment carries an "
                                        "amount on both sides", 0, ">= 1"))
                else:
                    amt = [float(live["amount"]) / float(local["amount"])
                           for live, local in amount_pairs]
                    ok = all(_rel(r, 1.0) <= AMOUNT_TOL_REL for r in amt)
                    checks.append(check("U3", name, PASS if ok else FAIL,
                                        "amount ratio ~ 1.00 on %d sessions (yuan, no "
                                        "10k scaling)" % len(amt),
                                        [round(r, 4) for r in amt],
                                        {"ratio": 1.0, "tolerance": AMOUNT_TOL_REL}))

            # B4 (advisory) ---------------------------------------------------------
            checks.append(check("B4", name, ADVISORY,
                                "the close ratio is %s; a step is evidence that the live "
                                "series is unadjusted relative to the cached qfq series, "
                                "not proof (the reference mixes fetch times)"
                                % ("flat" if step is None else "stepped at %s"
                                   % pairs[step][0]),
                                {"step_date": pairs[step][0] if step is not None else None},
                                None, kind="advisory"))

        # C1 / C2 / C3 --------------------------------------------------------------
        span = sorted({r["trade_date"] for r in ref if float(r.get("volume") or 0) > 0})
        live_dates = {r["date"] for r in rows}
        missing_span = [d for d in span if d not in live_dates]
        first_date = rows[0]["date"] if rows else None
        last_date = rows[-1]["date"] if rows else None
        research_present = len([d for d in live_dates
                                if cap.RESEARCH_START <= d <= cap.RESEARCH_END])
        warmup_present = len([d for d in live_dates
                              if cap.WARMUP_START <= d <= cap.WARMUP_END])
        coverage = {"first_date": first_date, "last_date": last_date,
                    "span_sessions": len(span),
                    "span_missing": missing_span[:20],
                    "research_sessions_present": research_present,
                    "warmup_sessions_present": warmup_present}

        if name == "bj920000":
            classification = ("pre_boundary_history_served"
                              if first_date and first_date < cap.BJ_CODE_BOUNDARY
                              else "post_boundary_only")
            summary = request_summary(name)
            checks.append(check("C2", name, FINDING,
                                "BJ outcome %r from the decoded KLC history body%s; the "
                                "CAUSE (code mapping or otherwise) is NOT established by "
                                "this observation"
                                % (classification,
                                   " (auxiliary outstanding-share evidence ABSENT: "
                                   "inconclusive, not an absence finding)"
                                   if aux_missing else ""),
                                {"classification": classification,
                                 "cause": "not established", "decided_by": "klc",
                                 "auxiliary_evidence": ("absent" if aux_missing
                                                        else "present"),
                                 **{"%s_request" % k: v for k, v in summary.items()},
                                 **coverage},
                                None, kind="finding"))
            span_ok = not missing_span
            checks.append(check("C2span", name, PASS if span_ok else FAIL,
                                "every reference session with volume appears live"
                                if span_ok else "%d reference sessions are missing live"
                                % len(missing_span), missing_span[:10], []))
        else:
            cid = "C1" if klass == "stock" else "C3"
            ref_tail = span[-1] if span else None
            ok = (first_date is not None and first_date <= cap.WINDOW_START
                  and (ref_tail is None or (last_date or "") >= ref_tail)
                  and not missing_span)
            checks.append(check(cid, name, PASS if ok else FAIL,
                                "first %s <= %s, last %s >= reference tail %s, span "
                                "complete" % (first_date, cap.WINDOW_START, last_date,
                                              ref_tail)
                                if ok else "coverage incomplete", coverage,
                                {"first_date": "<= %s" % cap.WINDOW_START,
                                 "span_missing": 0}))

        # C4 (finding) ---------------------------------------------------------------
        if klass == "stock":
            key = ("open", "high", "low", "close", "volume", "amount")
            seen, duplicate = set(), 0
            for r in in_window:
                tup = tuple(r.get(k) for k in key)
                if tup in seen:
                    duplicate += 1
                seen.add(tup)
            replay_info = replay.get(name, {}) if isinstance(replay, dict) else {}
            fabricated = sorted(set(replay_info.get("dates", [])) - live_dates)
            # R2-C: the share-dependent statistics mean something only when the share
            # series exists. Reporting "0 klc rows before the first share date None" read
            # as a measured zero loss when in fact nothing had been measured.
            if share_series:
                share_dates = {r["date"] for r in share_series}
                usable_dates = {r["date"] for r in share_series if r.get("usable")}
                first_share = min(usable_dates) if usable_dates else None
                before_share = len([d for d in live_dates
                                    if first_share and d < first_share])
                orphan_share = len([d for d in share_dates if d not in live_dates])
                measured = {
                    "duplicate_ohlcva_rows": duplicate,
                    "share_series_available": True,
                    "first_usable_share_date": first_share,
                    "klc_rows_before_first_usable_share": before_share,
                    "share_dates_without_klc": orphan_share,
                    "effective_first_date": max(
                        [d for d in [first_date, first_share] if d] or [None]),
                }
                detail = ("adapter post-processing: %d duplicate OHLCVA rows, %d klc rows "
                          "before the first usable share date %s, %d share dates with no "
                          "klc row" % (duplicate, before_share, first_share, orphan_share))
            else:
                measured = {
                    "duplicate_ohlcva_rows": duplicate,
                    "share_series_available": False,
                    "share_dependent_statistics": ("NOT MEASURED - the auxiliary series is "
                                                   "unavailable for this job"),
                }
                detail = ("adapter post-processing: %d duplicate OHLCVA rows measured. The "
                          "share-dependent statistics are NOT MEASURED because the "
                          "outstanding-share series is unavailable - absence of "
                          "measurement, not a measured zero loss" % duplicate)
            checks.append(check("C4", name, FINDING, detail, measured, None,
                                kind="finding"))
            # R2-C: assert what actually came back, not merely that nothing raised; and
            # say accurately WHY a replay is missing. The previous text claimed the
            # auxiliary body "was not captured" when in run 2 it was captured and failed
            # to parse - a different fact with a different remedy.
            status, detail = _replay_verdict(replay_info, fabricated, aux_missing,
                                             replay_error)
            observed = {k: replay_info.get(k) for k in
                        ("rows", "first_date", "last_date", "columns")}
            observed["dates_returned"] = len(replay_info.get("dates") or [])
            checks.append(check("R1", name, status, detail, observed,
                                {"fabricated_dates": 0, "rows": "> 0",
                                 "dates_returned": "== rows, bounded by first/last",
                                 "window": "%s..%s (dates within %s..%s)"
                                           % (REPLAY_START, REPLAY_END,
                                              cap.WINDOW_START, cap.WINDOW_END)}))
        else:
            replay_info = replay.get(name, {}) if isinstance(replay, dict) else {}
            fabricated = sorted(set(replay_info.get("dates", [])) - live_dates)
            # The index adapter takes no date arguments - it returns the whole served
            # series - so its expectation differs from the stock path on purpose.
            status, detail = _replay_verdict(replay_info, fabricated, False,
                                             replay_error, window=None,
                                             label="index adapter")
            observed = {k: replay_info.get(k) for k in
                        ("rows", "first_date", "last_date", "columns")}
            observed["dates_returned"] = len(replay_info.get("dates") or [])
            checks.append(check("R1", name, status, detail, observed,
                                {"fabricated_dates": 0, "rows": "> 0",
                                 "dates_returned": "== rows, bounded by first/last",
                                 "window": "not applicable to the index interface"}))

    if isinstance(replay, dict) and replay.get("_requested_urls") is not None:
        unexpected = [u for u in replay["_requested_urls"] if u not in bodies]
        checks.append(check("R1urls", "run", PASS if not unexpected else FAIL,
                            "the adapter requested only captured URLs" if not unexpected
                            else "the adapter requested uncaptured URLs: %s" % unexpected,
                            replay["_requested_urls"], sorted(bodies)))

    # ------------------------------------------------------------------- the verdicts
    verdicts = summarize(manifest, job_results, checks, outcomes)

    deterministic = {
        "schema": "m2b.checks.v1",
        "calendar_sha256": calendar_sha,
        # The RECOMPUTED hash of the retained reference content. Copying the declared
        # field meant that changing every stored unit and timestamp left the
        # deterministic hash identical, so a replay could not detect altered evidence.
        "reference_content_sha256": reference_content_sha,
        "body_sha256": {str(i): records[i].get("body_sha256") for i in sorted(records)
                        if records[i].get("body_sha256")},
        "outcomes": outcomes,
        "job_results": job_results,
        "checks": checks,
        "verdicts": verdicts,
        "adapter_basis_facts": basis_facts,
        "decoded_summary": {
            str(i): {k: decoded[i].get(k) for k in
                     ("js_variable", "branch", "branch_code", "row_count",
                      "observed_keys")}
            for i in sorted(decoded) if "rows" in decoded[i]},
    }
    run_meta = {"deadline_source": deadline_source,
                "deadline": deadline.snapshot(),
                "run_id": manifest.get("run_id"),
                "started_at_utc": manifest.get("started_at_utc"),
                "finished_at_utc": manifest.get("finished_at_utc"),
                "run_status": manifest.get("run_status"),
                "abort_reason": manifest.get("abort_reason"),
                "checked_at_utc": _dt.datetime.now(_dt.timezone.utc)
                .strftime("%Y-%m-%dT%H:%M:%SZ")}
    return {"deterministic": deterministic,
            "deterministic_sha256": cap.canonical_sha256(deterministic),
            "run_meta": run_meta}


def summarize(manifest, job_results, checks, outcomes):
    """Run status, per-job verdicts and ONE capability verdict, deterministically."""
    aborts = [r for info in outcomes.values() for r in info["requests"] if r["aborts_run"]]
    abort_reason = manifest.get("abort_reason")
    run_status = manifest.get("run_status", "completed")

    per_job = {}
    for job in cap.JOBS:
        name = job["job"]
        result = job_results[name]
        job_checks = [c for c in checks if c["symbol"] == name and c["kind"] == "required"]
        if result in (JOB_CONTINUE, JOB_INCONCLUSIVE_AUXILIARY):
            # R4: with the auxiliary evidence missing the history checks still ran; a
            # history FAIL is a FAIL, and otherwise the job is INCONCLUSIVE, never PASS.
            if any(c["status"] == FAIL for c in job_checks):
                per_job[name] = FAIL
            elif (result == JOB_INCONCLUSIVE_AUXILIARY
                  or any(c["status"] == INCONCLUSIVE for c in job_checks)):
                per_job[name] = INCONCLUSIVE
            else:
                per_job[name] = PASS
        elif result == JOB_NOT_SERVED:
            per_job[name] = JOB_NOT_SERVED
        elif result == JOB_FAILED:
            per_job[name] = FAIL
        else:
            per_job[name] = INCONCLUSIVE

    run_checks_failed = [c for c in checks
                         if c["symbol"] == "run" and c["status"] == FAIL]
    run_checks_unclear = [c for c in checks
                          if c["symbol"] == "run" and c["status"] == INCONCLUSIVE]

    capability = CAPABILITY_PASS
    reasons = []
    if run_checks_failed:
        capability = CAPABILITY_FAIL
        reasons.append("run-level checks failed: %s"
                       % sorted({c["id"] for c in run_checks_failed}))
    elif run_checks_unclear:
        capability = CAPABILITY_INCONCLUSIVE
        reasons.append("run-level checks are inconclusive: %s"
                       % sorted({c["id"] for c in run_checks_unclear}))
    for name, verdict in per_job.items():
        if verdict == FAIL:
            capability = CAPABILITY_FAIL
            reasons.append("%s FAILED" % name)
        elif verdict == INCONCLUSIVE and capability != CAPABILITY_FAIL:
            capability = CAPABILITY_INCONCLUSIVE
            reasons.append("%s INCONCLUSIVE" % name)
        elif verdict == JOB_NOT_SERVED:
            if name != "bj920000":
                capability = CAPABILITY_FAIL
                reasons.append("%s returned an explicit absence; only the BJ job may "
                               "do so as a finding" % name)
            elif capability == CAPABILITY_PASS:
                capability = CAPABILITY_PASS_BJ
                reasons.append("bj920000: vendor_explicit_absence_at_path, documented as "
                               "a bounded observation with an unestablished cause")
    if run_status != "completed":
        if aborts and any(r["evidence_class"] == "run_aborted_vendor_stop" for r in aborts):
            capability = CAPABILITY_FAIL
            reasons.append("the vendor stopped the run (403/429)")
        elif capability != CAPABILITY_FAIL:
            capability = CAPABILITY_INCONCLUSIVE
            reasons.append("the run aborted: %s" % abort_reason)

    return {"run_status": run_status, "abort_reason": abort_reason,
            "per_job": per_job, "capability": capability, "reasons": reasons,
            "authorizes_pilot": False,
            "note": ("a capability verdict concerns five captured responses and the "
                     "decoder, never corpus readiness, feature readiness or training; "
                     "%s is not an unqualified PASS and authorizes nothing"
                     % CAPABILITY_PASS_BJ)}


# ============================================================== replay and reporting
def replay(evidence_dir, *, calendar_path=cap.CALENDAR, replay_fn=adapter_replay,
           routine=None, routine_sha256=dec.HK_JS_DECODE_SHA256, racer_factory=None,
           budget_sec=cap.REPLAY_BUDGET_SEC, clock=None):
    """Recompute the deterministic block from retained evidence, opening no database.

    A replay is a DIFFERENT run from the capture, so it states its own budget rather than
    inheriting an exhausted one. That is the only place a fresh deadline is legitimate;
    an initial run's phases share one.
    """
    evidence_dir = Path(evidence_dir)
    manifest = json.loads((evidence_dir / "capture_manifest.json")
                          .read_text(encoding="utf-8"))
    extract = json.loads((evidence_dir / "reference" / "reference_extract.json")
                         .read_text(encoding="utf-8"))
    with cap.db_guard("replay must not open a production database"):
        result = run_checks(manifest=manifest, raw_dir=evidence_dir / "raw",
                            reference_extract=extract, calendar_path=calendar_path,
                            replay_fn=replay_fn, routine=routine,
                            routine_sha256=routine_sha256,
                            racer_factory=racer_factory,
                            deadline=cap.Deadline(budget_sec,
                                                  clock=clock or time.monotonic,
                                                  label="offline replay"))
    stored = evidence_dir / "checks.json"
    if stored.exists():
        previous = json.loads(stored.read_text(encoding="utf-8"))
        result["matches_stored"] = (previous.get("deterministic_sha256")
                                    == result["deterministic_sha256"])
        result["stored_sha256"] = previous.get("deterministic_sha256")
    return result


def render_report(result, manifest):
    d = result["deterministic"]
    v = d["verdicts"]
    lines = ["# M2b smoke report", "",
             "run_id: %s" % result["run_meta"].get("run_id"),
             "run status: %s" % v["run_status"],
             "abort reason: %s" % (v["abort_reason"] or "none"), "",
             "## Verdicts", "",
             "| scope | verdict |", "|---|---|"]
    for name, verdict in v["per_job"].items():
        lines.append("| job %s | %s |" % (name, verdict))
    lines.append("| capability | **%s** |" % v["capability"])
    lines += ["", "Reasons: %s" % ("; ".join(v["reasons"]) or "none"), "",
              v["note"], "",
              "## Outcome table results", "",
              "| # | job | transport | payload | request | job | evidence | skipped rest |",
              "|---|---|---|---|---|---|---|---|"]
    for job, info in d["outcomes"].items():
        for row in info["requests"]:
            lines.append("| %d | %s | %s | %s | %s | %s | %s | %s |"
                         % (row["index"], job, row["transport_state"],
                            row["payload_state"], row["request_result"],
                            row["job_result"], row["evidence_class"],
                            row["skip_remaining"]))
    lines += ["", "## Checks", "",
              "| id | scope | kind | status | detail |", "|---|---|---|---|---|"]
    for c in d["checks"]:
        lines.append("| %s | %s | %s | %s | %s |"
                     % (c["id"], c["symbol"], c["kind"], c["status"],
                        str(c["detail"]).replace("|", "/")[:200]))
    lines += ["", "## Captured bodies", "", "| # | sha256 |", "|---|---|"]
    for index, digest in d["body_sha256"].items():
        lines.append("| %s | `%s` |" % (index, digest))
    lines += ["", "deterministic checks sha256: `%s`" % result["deterministic_sha256"],
              "reference content sha256 (recomputed): `%s`"
              % d["reference_content_sha256"],
              "", "This report makes no statement about corpus coverage, feature "
              "readiness, models or strategy."]
    return "\n".join(lines)
