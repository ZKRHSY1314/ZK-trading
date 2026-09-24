"""M2b - the ONE outcome table, shared by capture (P-A) and checks (P-C).

Why this module exists
----------------------
The first 1a delivery put the table in the checker only. Capture therefore treated every
HTTP 200 as a successful request: it issued a stock's second request after the first had
returned HTML, and two payload-failed jobs did not stop the third. The checker then
contradicted the capture about which requests should have been skipped.

The table now lives in one place that BOTH sides import, so a single decision decides:

* whether the response is usable at all (`classify_payload`),
* whether the job's remaining requests are issued (`skip_remaining`),
* whether the job counts as failed for the consecutive-failed-job stop,
* whether the run aborts (`aborts_run`),
* and, later, what the evidence means.

Because capture and checks read the same rows, the request count and the outcomes cannot
disagree: a request is skipped only because the table said so, and the checker can verify
that from the record.

Two properties hold by construction and are regression-tested:

* a transport failure, a TLS failure, a decoder error, an empty body or markup can never
  become a positive capability finding - they are FAILED or INCONCLUSIVE_* evidence;
* the only route to "the vendor does not serve this path" is an explicit HTTP 404/410,
  and even then the CAUSE is recorded as not established;
* (R4) that route is REQUEST-KIND specific: only the KLC history request can yield
  `NOT_SERVED_AT_PATH`. A 404/410 on the auxiliary outstanding-share endpoint, with the
  history body already received, is `INCONCLUSIVE_AUXILIARY` - the history checks still
  run on that body, and the missing auxiliary evidence can neither become a
  history-capability PASS nor mask a history-validation failure.
"""

from __future__ import annotations

import sina_klc_decoder as dec

# ------------------------------------------------------------------- result vocabulary
PASS, FAIL, ADVISORY, FINDING = "PASS", "FAIL", "ADVISORY", "FINDING"
INCONCLUSIVE = "INCONCLUSIVE"

CAPABILITY_PASS = "PASS"
CAPABILITY_PASS_BJ = "PASS_WITH_DOCUMENTED_BJ_NON_SERVICE"
CAPABILITY_INCONCLUSIVE = "INCONCLUSIVE"
CAPABILITY_FAIL = "FAIL"

JOB_FAILED = "FAILED"
JOB_INCONCLUSIVE_TRANSPORT = "INCONCLUSIVE_TRANSPORT"
JOB_INCONCLUSIVE_PAYLOAD = "INCONCLUSIVE_PAYLOAD"
JOB_INCONCLUSIVE_DECODE = "INCONCLUSIVE_DECODE"
JOB_NOT_SERVED = "NOT_SERVED_AT_PATH"
#: History served and decoded, but the auxiliary outstanding-share request failed, was
#: absent (404/410) or unusable. Inconclusive capability evidence; never an absence.
JOB_INCONCLUSIVE_AUXILIARY = "INCONCLUSIVE_AUXILIARY"
JOB_CONTINUE = "CONTINUE"

#: Why a request was not issued. A job-local skip needs an upstream trigger in the same
#: job; a run-global skip is explained by the run abort and needs no such trigger.
SKIP_JOB_LOCAL = "job_local"
SKIP_RUN_GLOBAL = "run_global"


def _row(transport_state, payload_state, request_result, job_result, evidence_class,
         skip_remaining, aborts_run, note):
    return {"transport_state": transport_state, "payload_state": payload_state,
            "request_result": request_result, "job_result": job_result,
            "evidence_class": evidence_class, "skip_remaining": skip_remaining,
            "aborts_run": aborts_run, "note": note}


OUTCOME_TABLE = (
    _row("ok", "decoded", "OK", JOB_CONTINUE, "decoded_payload", False, False,
         "the only state from which a job can PASS"),
    _row("ok", "markup", "BAD_PAYLOAD", JOB_INCONCLUSIVE_PAYLOAD, "inconclusive_payload",
         True, False, "markup is an upstream/portal answer, not evidence of non-service"),
    _row("ok", "empty", "BAD_PAYLOAD", JOB_INCONCLUSIVE_PAYLOAD, "inconclusive_payload",
         True, False, "an empty 200 does not distinguish non-service from a bad hop"),
    _row("ok", "undecodable", "BAD_DECODE", JOB_INCONCLUSIVE_DECODE, "inconclusive_decode",
         True, False, "a decoder error is our defect or a format change, never a finding"),
    _row("ok", "no_rows", "BAD_DECODE", JOB_INCONCLUSIVE_DECODE, "inconclusive_decode",
         True, False, "zero rows is unexplained, not a documented absence"),
    _row("vendor_not_found", "not_applicable", "VENDOR_ABSENT", JOB_NOT_SERVED,
         "vendor_explicit_absence_at_path", True, False,
         "HTTP 404/410 only: an explicit answer about THIS path; the cause is not "
         "established by it"),
    _row("vendor_stop", "not_applicable", "STOP", JOB_FAILED, "run_aborted_vendor_stop",
         True, True, "403/429 abort the whole run unconditionally and are never retried"),
    _row("exhausted_retryable", "not_applicable", "FAILED", JOB_FAILED,
         "inconclusive_transport", True, False,
         "exhausted 5xx/timeout/connection: a temporary upstream or network fault"),
    _row("non_retryable_status", "not_applicable", "FAILED", JOB_FAILED,
         "inconclusive_transport", True, False, "any other non-200 status"),
    _row("redirect", "not_applicable", "FAILED", JOB_FAILED, "inconclusive_transport",
         True, False, "a refused 3xx; following it would be an uncounted attempt"),
    _row("tls_failure", "not_applicable", "FAILED", JOB_FAILED, "inconclusive_transport",
         True, False,
         "a certificate/TLS failure is NEVER retried: repeating it cannot make an "
         "unauthenticated channel authentic"),
    _row("transport_error", "not_applicable", "FAILED", JOB_FAILED,
         "inconclusive_transport", True, False,
         "any other non-retryable exception"),
    _row("aborted", "not_applicable", "ABORTED", JOB_FAILED, "run_aborted", True, True,
         "the run-level deadline, ceiling or stop fired during this request"),
    _row("skipped", "not_applicable", "SKIPPED", JOB_CONTINUE, "skipped", False, False,
         "not issued, because the table skipped it; never counted as a success"),
)

_TABLE_INDEX = {(r["transport_state"], r["payload_state"]): r for r in OUTCOME_TABLE}
SEVERITY = {JOB_CONTINUE: 0, JOB_NOT_SERVED: 1, JOB_INCONCLUSIVE_PAYLOAD: 2,
            JOB_INCONCLUSIVE_DECODE: 2, JOB_INCONCLUSIVE_TRANSPORT: 2,
            JOB_INCONCLUSIVE_AUXILIARY: 2, JOB_FAILED: 3}


def aggregate_job(history, auxiliary):
    """`(job_result, note)` for one job from its `(record, row)` pairs, BY REQUEST KIND.

    The previous aggregation took the worst row of the job, so an explicit 404 on the
    auxiliary outstanding-share endpoint was promoted to the BJ history non-service
    exception although the history endpoint had served and decoded data. Now:

    * the KLC history request decides whether history was served. Its row's job result
      stands, and it is the ONLY request whose explicit 404/410 can yield
      `NOT_SERVED_AT_PATH`;
    * a history request never issued without a documented skip trigger is a
      contradiction: `FAILED`;
    * once history is decoded, an auxiliary request that failed, was explicitly absent,
      was aborted or returned an unusable payload is `INCONCLUSIVE_AUXILIARY`. The
      history checks still run on the body received, so invalid history is still found,
      and the missing auxiliary evidence can never become a PASS or an absence finding;
    * an auxiliary request skipped with no trigger stays a contradiction: `FAILED`.
    """
    if history is None:
        return JOB_FAILED, "no history request recorded for this job"
    history_record, history_row = history
    if history_row["job_result"] != JOB_CONTINUE:
        return history_row["job_result"], (
            "decided by the KLC history request: %s/%s"
            % (history_row["transport_state"], history_row["payload_state"]))
    if history_record.get("outcome") != "ok":
        if (history_record.get("outcome") == "skipped"
                and history_record.get("skip_scope") == SKIP_RUN_GLOBAL):
            return JOB_FAILED, ("the history request was never issued because the run "
                                "aborted first; the job cannot PASS")
        return JOB_FAILED, ("the history request was not issued and no earlier outcome "
                            "triggered a skip")
    if auxiliary is None:
        return JOB_CONTINUE, "history decoded; this instrument has no auxiliary request"
    auxiliary_record, auxiliary_row = auxiliary
    if auxiliary_record.get("outcome") == "ok" and auxiliary_row["job_result"] == JOB_CONTINUE:
        return JOB_CONTINUE, "history and auxiliary outstanding-share request both decoded"
    if auxiliary_row.get("aborts_run"):
        # The reviewed rows for a vendor stop and for a run abort are FAILED and abort
        # the run; an auxiliary request cannot soften them into inconclusive evidence.
        return JOB_FAILED, (
            "history decoded, but the auxiliary request %s the run (%s): a vendor stop "
            "or run abort is a FAILED job, never inconclusive auxiliary evidence"
            % ("stopped" if auxiliary_row["transport_state"] == "vendor_stop"
               else "aborted", auxiliary_row["evidence_class"]))
    if auxiliary_record.get("outcome") == "skipped":
        if auxiliary_record.get("skip_scope") == SKIP_RUN_GLOBAL:
            return JOB_INCONCLUSIVE_AUXILIARY, (
                "history decoded; the auxiliary request was never issued because the "
                "run aborted first (run-global skip): inconclusive auxiliary evidence, "
                "never a history-absence finding and never a PASS")
        return JOB_FAILED, ("the auxiliary request was skipped although the history "
                            "request decoded; no outcome triggered that skip")
    return JOB_INCONCLUSIVE_AUXILIARY, (
        "history served and decoded; the auxiliary outstanding-share request is %s/%s "
        "(%s). Missing auxiliary evidence is inconclusive capability evidence - never a "
        "history-absence finding and never a PASS"
        % (auxiliary_row["transport_state"], auxiliary_row["payload_state"],
           auxiliary_row["request_result"]))


def lookup_outcome(transport_state, payload_state="not_applicable"):
    """Exhaustive, deterministic. An unlisted pair is a bug, and fails closed."""
    key = (transport_state, payload_state)
    if key in _TABLE_INDEX:
        return _TABLE_INDEX[key]
    if transport_state != "ok":
        fallback = _TABLE_INDEX.get((transport_state, "not_applicable"))
        if fallback:
            return fallback
    return _row(transport_state, payload_state, "FAILED", JOB_FAILED,
                "inconclusive_transport", True, False,
                "unclassified state pair %r; failing closed" % (key,))


#: How the unchanged M2a transport classified an attempt -> our transport state. This is
#: the AUTHORITATIVE signal. An earlier version sniffed the error text for "transient",
#: which also matched "non-transient" - so a TLS failure was classified as a retryable
#: network fault. Failure classification is never derived from a message here.
ATTEMPT_OUTCOME_STATES = {
    "transient": "exhausted_retryable",
    "retryable": "exhausted_retryable",
    "redirect": "redirect",
    "stop": "vendor_stop",
    "error": "transport_error",
    "failed": "non_retryable_status",
}


def transport_state_of(record):
    """Map one recorded request onto a transport state. No interpretation beyond this."""
    outcome = record.get("outcome")
    status = record.get("status")
    if outcome == "skipped":
        return "skipped"
    if outcome == "aborted":
        # A 403/429 latched from the headers aborts the run through RunAborted, so the
        # record is `aborted` and carries the vendor's status: it stays a vendor stop.
        return "vendor_stop" if status in (403, 429) else "aborted"
    if outcome == "ok":
        return "ok" if status == 200 else "non_retryable_status"
    if record.get("failure_kind") == "tls":
        # Recorded by the live adapter itself, before the broad connection-error mapping.
        return "tls_failure"
    if status in (403, 429):
        return "vendor_stop"
    if status in (404, 410):
        return "vendor_not_found"
    if status is not None and 300 <= int(status) < 400:
        return "redirect"
    attempt = record.get("transport_outcome")
    if attempt in ATTEMPT_OUTCOME_STATES:
        return ATTEMPT_OUTCOME_STATES[attempt]
    if record.get("retryable"):
        return "exhausted_retryable"
    if status is None:
        # Nothing classified it as transient, so it stays non-retryable evidence.
        return "transport_error"
    return "non_retryable_status"


# ------------------------------------------------------------------ payload states
def classify_payload(content, kind, *, encoding=None, routine=None,
                     routine_sha256=dec.HK_JS_DECODE_SHA256, racer_factory=None,
                     expected_symbol=None, instrument_class="stock"):
    """`(payload_state, decoded_or_None, reason_or_None)` for one captured body.

    Capture calls this BEFORE deciding whether to issue the job's next request, and the
    checker calls it again on the retained bytes. Same function, same states, so the two
    can never disagree about what a body was.
    """
    if not content:
        return "empty", None, "zero bytes captured"
    try:
        text = dec.bytes_to_text(content, encoding)
    except dec.DecodeError as exc:
        return "undecodable", None, str(exc)
    if not text.strip():
        return "empty", None, "body is blank"
    lowered = text.lstrip()[:16].lower()
    if any(lowered.startswith(prefix.lower()) for prefix in dec.MARKUP_PREFIXES):
        return "markup", None, "body is markup, not a JS assignment"
    try:
        if kind == "klc":
            if routine is None:
                from akshare.stock.cons import hk_js_decode as routine
            decoded = dec.decode_klc(
                content, encoding, routine=routine,
                expected_routine_sha256=routine_sha256,
                racer_factory=racer_factory or dec.default_racer_factory)
        else:
            decoded = {"share_series": dec.parse_outstanding_share(
                content, encoding, expected_symbol=expected_symbol,
                instrument_class=instrument_class)}
    except dec.DecodeError as exc:
        if "zero rows" in str(exc) or "non-empty list" in str(exc):
            return "no_rows", None, str(exc)
        return "undecodable", None, str(exc)
    return "decoded", decoded, None


# ------------------------------------------------- the frozen selection/threshold contract
#: Defined ONCE, here, because two modules must agree on it without importing each other:
#: `smoke_capture` freezes it into the reference extract at capture time, and
#: `smoke_checks` applies it. EV5 then compares the RETAINED contract against the values
#: the running checks actually use, so altered retained evidence is detected instead of
#: being described by an unused field.
THRESHOLDS = {
    "identity_sessions": 10,
    "min_segment_sessions": 3,
    "price_tol_rel": 0.001,
    "volume_tol_rel": 0.01,
    "amount_tol_rel": 0.01,
    "volume_ratio_stock": 100.0,
    "volume_ratio_index": 1.0,
}
BASIS_EXPECTED = {"stock": "qfq", "benchmark": "none"}
