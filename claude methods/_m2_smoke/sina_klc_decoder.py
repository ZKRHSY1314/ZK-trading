"""M2b P-B - a pure decoder for the REAL Sina payloads. No I/O, no network, no clock.

Scope
-----
This module turns captured response bytes into rows. It never opens a socket, a file or
a database, and it holds no state, so the same bytes always produce the same rows. That
is what makes the boundary-1b reviewer reproduction (Section 8 of the request) possible:
re-running this module on the retained `raw/*.bin` must reproduce `checks.json`.

It is deliberately NOT the M2a decoder. `_m2_pilot/decoder.py` accepts only the synthetic
`m2a.market.v1` envelope and registers `sina.klc_kl.js` as KNOWN-UNSUPPORTED; that
registration stays true, and nothing here is imported by the validated M2a code.

Fail-closed rules
-----------------
* bytes -> text is `errors="strict"`. `requests` uses `errors="replace"` for
  `Response.text`, so a strict failure here means the adapter silently substituted U+FFFD.
  P-C compares this function's output against the captured `response.text` hash, so the
  substitution becomes a visible FAIL instead of a quiet corruption.
* The payload must be extracted two independent ways - a strict regex and the adapter's
  own `split("=")[1].split(";")[0]` - and both must agree. If they disagree, the vendor
  format moved under the adapter and we say so rather than guessing.
* Markup, an empty body, a body that does not start with `var`, a JS evaluation error,
  zero rows, duplicate/unparseable dates and non-numeric fields all raise.

Resource limits (S1)
--------------------
Decoding is bounded: payload length, row count, JS wall-clock (`timeout_sec`) and JS heap
(`max_memory`) all have finite caps, so a hostile or corrupt body cannot spin the run
past its deadline.

The JS routine and the JS engine are INJECTED. Tests drive this module with a fake racer
and never need `py_mini_racer`; the real run passes the pinned `hk_js_decode` whose
SHA-256 is verified here, in this module, before it is evaluated.
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import re

# ---------------------------------------------------------------------------- limits
MAX_BODY_BYTES = 8 * 1024 * 1024
MAX_PAYLOAD_CHARS = 4_000_000
MAX_ROWS = 20_000
DECODE_TIMEOUT_SEC = 20.0
DECODE_MAX_MEMORY = 256 * 1024 * 1024

#: The pinned vendor routine. Verified before evaluation; see F4.
HK_JS_DECODE_SHA256 = "39a599c94dde4df1c2eb0882d4bff9560160cfd52ead0797cebb04b3122c2f52"

#: `hk_js_decode` dispatches on the first 12 bits of the payload (`cons.py` `w([12, 6])`
#: then `{_1479: D, _136: _, _200: C, _139: R, _197: A, _3466: O}["_" + u[0]]`). Only
#: branch `O` emits `amount`. We read the same 12 bits here so the branch is OBSERVED
#: rather than guessed from which keys happen to come back.
BRANCHES = {1479: "D", 136: "_", 200: "C", 139: "R", 197: "A", 3466: "O"}
B64_ALPHABET = ("ABCDEFGHIJKLMNOPQRSTUVWXYZ"
                "abcdefghijklmnopqrstuvwxyz"
                "0123456789+/")
_B64_INDEX = {ch: i for i, ch in enumerate(B64_ALPHABET)}

STOCK_REQUIRED_KEYS = ("date", "open", "high", "low", "close", "volume", "amount")
INDEX_REQUIRED_KEYS = ("date", "open", "high", "low", "close", "volume")
#: Keys the vendor may add. Anything outside this set plus the required keys is reported.
OPTIONAL_KEYS = ("prevclose", "postVol", "postAmt")

MARKUP_PREFIXES = ("<!doctype", "<html", "<?xml", "<!DOCTYPE")
#: The assignment itself, anchored at the start and ending at its semicolon. What may
#: follow is validated separately by `_scan_trailer` - deliberately NOT by widening this
#: pattern, because a regex that merely tolerates "something after" would also tolerate
#: executable JavaScript.
_VAR_RE = re.compile(r'^\s*var\s+(\w+)\s*=\s*"([^"]*)"\s*;')
_NUMERIC_KEYS = ("open", "high", "low", "close", "volume", "amount",
                 "prevclose", "postVol", "postAmt")

#: Bounds on the trailer. Both retained real bodies carry a single block comment of 281
#: and 308 characters; these caps leave room for that without admitting a large blob.
MAX_TRAILER_CHARS = 8192
MAX_TRAILER_COMMENTS = 8


class DecodeError(Exception):
    """The captured bytes are not a payload we can honestly turn into rows."""


# ------------------------------------------------------------------- bytes -> text
def bytes_to_text(content, encoding, *, fallback="utf-8"):
    """The bytes-to-text step, strictly.

    `encoding` is the `response.encoding` recorded at capture time; `fallback` is used
    only when the response declared none. A `UnicodeDecodeError` here is a finding, not
    something to paper over with `errors="replace"`.
    """
    if not isinstance(content, (bytes, bytearray)):
        raise DecodeError("expected bytes, got %s" % type(content).__name__)
    if len(content) == 0:
        raise DecodeError("empty body: zero bytes captured")
    if len(content) > MAX_BODY_BYTES:
        raise DecodeError("body of %d bytes exceeds the %d-byte limit"
                          % (len(content), MAX_BODY_BYTES))
    codec = encoding or fallback
    try:
        return bytes(content).decode(codec, errors="strict")
    except (LookupError, UnicodeDecodeError) as exc:
        raise DecodeError("bytes do not decode as %r: %s" % (codec, exc)) from exc


def sha256_text(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# --------------------------------------------------------------- payload extraction
def _scan_trailer(rest):
    """Validate what follows the assignment. Only whitespace and CLOSED block comments.

    D1. The live bodies captured on 2026-09-08 are an assignment followed by a
    non-executable block comment:

        var KLC_K2_sh600011="<73,050 chars>";\\n\\n/* <281 chars> */

    The original extractor required the body to END at the assignment, so it rejected
    both real bodies. Widening it had to be done without admitting arbitrary trailing
    JavaScript, so this is a scanner rather than a looser pattern: it walks the remainder
    and accepts ONLY whitespace and complete `/* ... */` blocks. Anything else - a second
    statement, another assignment, a bare identifier, a line comment, an unterminated
    comment - is refused, because none of those was observed and each could execute or
    hide something that does.

    Returns a description of the trailer for the evidence record.
    """
    if len(rest) > MAX_TRAILER_CHARS:
        raise DecodeError("trailing content of %d chars exceeds the %d-char limit"
                          % (len(rest), MAX_TRAILER_CHARS))
    comments = []
    index = 0
    while index < len(rest):
        if rest[index].isspace():
            index += 1
            continue
        if not rest.startswith("/*", index):
            raise DecodeError(
                "unexpected trailing content after the assignment at offset %d (%r); only "
                "whitespace and closed /* */ comments are accepted, so that no executable "
                "JavaScript can follow the payload" % (index, rest[index:index + 40]))
        end = rest.find("*/", index + 2)
        if end < 0:
            raise DecodeError("unterminated block comment in the trailing content; "
                              "refusing a body whose trailer does not close")
        comments.append(end + 2 - index)
        if len(comments) > MAX_TRAILER_COMMENTS:
            raise DecodeError("more than %d trailing comments; refusing"
                              % MAX_TRAILER_COMMENTS)
        index = end + 2
    return {"trailer_chars": len(rest), "comment_count": len(comments),
            "comment_chars": comments}


def extract_payload(text, *, with_trailer=False):
    """Return `(js_variable_name, payload)`; raise unless both extractions agree.

    The adapter's extraction is `text.split("=")[1].split(";")[0].replace('"', "")`
    (`stock_zh_a_sina.py:181`, `index_stock_zh.py:306`). It is positional and would
    silently truncate at an unexpected `=`. We therefore also parse the assignment
    strictly and require the two to produce the same string - a check the real bodies
    pass, including `sh000300` whose trailer contains base64 padding `=`.

    `with_trailer=True` additionally returns what followed the assignment, for the record.
    """
    stripped = text.lstrip()
    lowered = stripped[:16].lower()
    for prefix in MARKUP_PREFIXES:
        if lowered.startswith(prefix.lower()):
            raise DecodeError("body is markup, not a JS assignment (starts %r)"
                              % stripped[:40])
    if not stripped:
        raise DecodeError("body is blank after stripping whitespace")
    if not stripped.startswith("var"):
        raise DecodeError("body does not start with 'var' (starts %r)" % stripped[:40])

    match = _VAR_RE.match(text)
    if not match:
        raise DecodeError("body is not a single quoted `var NAME = \"...\";` assignment")
    name, payload = match.group(1), match.group(2)
    trailer = _scan_trailer(text[match.end():])

    try:
        adapter_payload = text.split("=")[1].split(";")[0].replace('"', "")
    except IndexError:
        raise DecodeError("the adapter's own extraction finds no '=' in the body") from None
    if adapter_payload != payload:
        raise DecodeError(
            "the adapter's positional extraction and a strict parse disagree "
            "(adapter %d chars, strict %d chars); the vendor format moved"
            % (len(adapter_payload), len(payload)))

    if not payload:
        raise DecodeError("the assignment carries an empty payload")
    if len(payload) > MAX_PAYLOAD_CHARS:
        raise DecodeError("payload of %d chars exceeds the %d-char limit"
                          % (len(payload), MAX_PAYLOAD_CHARS))
    if with_trailer:
        return name, payload, trailer
    return name, payload


def header_branch(payload):
    """The 12-bit header the routine dispatches on, read independently of the routine.

    `u = w([12, 6])` reads 12 bits LSB-first across the first two base64 characters, so
    `u[0] = index(p0) | index(p1) << 6`.
    """
    if len(payload) < 2:
        raise DecodeError("payload is too short to carry a 12-bit header")
    try:
        low = _B64_INDEX[payload[0]]
        high = _B64_INDEX[payload[1]]
    except KeyError as exc:
        raise DecodeError("payload character %r is outside the base64 alphabet"
                          % (exc.args[0],)) from None
    code = low | (high << 6)
    return code, BRANCHES.get(code)


# ------------------------------------------------------------------------- decoding
def default_racer_factory():                          # pragma: no cover - needs the engine
    """The real engine. Imported lazily so tests never need it."""
    import py_mini_racer

    return py_mini_racer.MiniRacer()


def _normalize_date(value):
    """Accept what the engine actually returns and refuse anything ambiguous.

    `hk_js_decode` builds `new Date((u + r.d) * 864e5)`, i.e. midnight UTC, and
    mini-racer hands that back as a tz-aware `datetime`. A non-midnight or non-UTC
    timestamp would mean a timezone shifted the trading day, which must not be rounded
    away silently.
    """
    if isinstance(value, _dt.datetime):
        if value.tzinfo is not None and value.utcoffset() != _dt.timedelta(0):
            raise DecodeError("date %r is not UTC; a timezone shift would move the "
                              "trading day" % (value,))
        if (value.hour, value.minute, value.second, value.microsecond) != (0, 0, 0, 0):
            raise DecodeError("date %r carries a time-of-day component" % (value,))
        return value.date().isoformat()
    if isinstance(value, _dt.date):
        return value.isoformat()
    if isinstance(value, str):
        head = value[:10]
        tail = value[10:]
        if tail and not (tail.startswith("T") or tail.startswith(" ")):
            raise DecodeError("unparseable date %r" % (value,))
        if tail:
            rest = tail[1:]
            if rest not in ("", "Z") and not rest.startswith("00:00:00"):
                raise DecodeError("date %r carries a time-of-day component" % (value,))
        try:
            return _dt.date.fromisoformat(head).isoformat()
        except ValueError:
            raise DecodeError("unparseable date %r" % (value,)) from None
    raise DecodeError("date field has unexpected type %s" % type(value).__name__)


def _to_number(key, value):
    if isinstance(value, bool):
        raise DecodeError("field %r is a boolean, not a number" % key)
    if isinstance(value, (int, float)):
        number = float(value)
    elif isinstance(value, str):
        try:
            number = float(value.strip())
        except ValueError:
            raise DecodeError("field %r is not numeric: %r" % (key, value)) from None
    else:
        raise DecodeError("field %r has unexpected type %s" % (key, type(value).__name__))
    if number != number or number in (float("inf"), float("-inf")):
        raise DecodeError("field %r is not finite: %r" % (key, value))
    return number


def decode_klc(content, encoding, *, routine, racer_factory=default_racer_factory,
               expected_routine_sha256=HK_JS_DECODE_SHA256,
               timeout_sec=DECODE_TIMEOUT_SEC, max_memory=DECODE_MAX_MEMORY,
               max_rows=MAX_ROWS):
    """Captured bytes -> `{"rows": [...], "js_variable": ..., "branch": ...}`.

    Keys are kept exactly as the routine names them. No positional renaming happens
    anywhere: a row that lacks `amount` is reported without `amount`, never given one.
    """
    if expected_routine_sha256 is not None:
        actual = hashlib.sha256(routine.encode("utf-8")).hexdigest()
        if actual != expected_routine_sha256:
            raise DecodeError(
                "the vendor routine changed (sha256 %s, pinned %s); refusing to decode "
                "with an unpinned routine" % (actual[:16], expected_routine_sha256[:16]))

    text = bytes_to_text(content, encoding)
    name, payload, trailer = extract_payload(text, with_trailer=True)
    branch_code, branch = header_branch(payload)

    racer = racer_factory()
    try:
        racer.eval(routine, timeout_sec=timeout_sec, max_memory=max_memory)
        raw_rows = racer.call("d", payload, timeout_sec=timeout_sec, max_memory=max_memory)
    except DecodeError:
        raise
    except Exception as exc:                          # noqa: BLE001 - engine-specific
        raise DecodeError("the JS routine failed on this body (%s: %s)"
                          % (type(exc).__name__, exc)) from exc

    try:
        length = len(raw_rows)
    except TypeError:
        raise DecodeError("the routine returned %s, not a list of records"
                          % type(raw_rows).__name__) from None
    if length == 0:
        raise DecodeError("the routine returned zero rows")
    if length > max_rows:
        raise DecodeError("the routine returned %d rows, above the %d-row limit"
                          % (length, max_rows))

    rows = []
    for index in range(length):
        try:
            record = dict(raw_rows[index])
        except Exception as exc:                      # noqa: BLE001
            raise DecodeError("record %d is not a mapping (%s)" % (index, exc)) from exc
        if "date" not in record:
            raise DecodeError("record %d carries no date" % index)
        row = {"date": _normalize_date(record["date"])}
        for key, value in record.items():
            if key == "date":
                continue
            row[key] = _to_number(key, value) if key in _NUMERIC_KEYS else value
        rows.append(row)

    dates = [r["date"] for r in rows]
    duplicates = sorted({d for d in dates if dates.count(d) > 1})
    if duplicates:
        raise DecodeError("duplicate dates in the decoded series: %s" % duplicates[:5])
    if dates != sorted(dates):
        raise DecodeError("decoded dates are not strictly increasing")

    observed_keys = sorted({k for r in rows for k in r})
    return {"rows": rows, "js_variable": name, "branch": branch,
            "branch_code": branch_code, "observed_keys": observed_keys,
            "payload_chars": len(payload), "text_sha256": sha256_text(text),
            "row_count": len(rows), "trailer": trailer}


# ------------------------------------------------------ request #2 / #5: JSONP series
#: The vendor reports this series in 万股. `stock_zh_a_sina.py:207` multiplies it by
#: 10,000 to obtain shares and `:208` divides volume by the result to get turnover. It is
#: NEVER traded amount, whatever the vendor calls the JSON field.
OUTSTANDING_SHARE_WAN_TO_SHARES = 10_000

#: The exact JS variable name per request kind. `KLC_K2_` is the stock history path
#: (`hisdata_klc2`), `KLC_KL_` the index path (`hisdata`), `KKE_ShareAmount_` the
#: auxiliary endpoint. Observed on every retained body from both captures.
_VARIABLE_PREFIXES = {
    ("klc", "stock"): "KLC_K2",
    ("klc", "benchmark"): "KLC_KL",
    ("outstanding_share", "stock"): "KKE_ShareAmount",
    ("outstanding_share", "benchmark"): "KKE_ShareAmount",
}

_JSONP_RE = re.compile(
    r'^\s*(?:/\*.*?\*/\s*)*var\s+(\w+)\s*=\s*\(\s*(\[.*\])\s*\)\s*;', re.DOTALL)


def expected_js_variable(kind, instrument_class, adapter_symbol):
    """The complete variable name this request must carry, exchange and code included.

    R2-B. The previous check collected every digit out of the name and asked whether the
    result was a substring of the symbol. `KLC_K2_sh600011` yields `2600011` - the `2`
    comes from the `K2` prefix - which is not a substring of `sh600011`, so a body that
    had just decoded correctly was failed. `KLC_KL_sh000300` yields `000300` and passed,
    which is why only the stock path showed the bug. Structure is matched here instead:
    prefix by request kind and instrument class, then the exact adapter symbol.
    """
    try:
        prefix = _VARIABLE_PREFIXES[(kind, instrument_class)]
    except KeyError:
        raise DecodeError("no variable-name grammar for kind %r / class %r"
                          % (kind, instrument_class)) from None
    return "%s_%s" % (prefix, adapter_symbol)


def check_js_variable(observed, kind, instrument_class, adapter_symbol):
    """`(ok, reason)` - the observed name must equal the expected one exactly."""
    expected = expected_js_variable(kind, instrument_class, adapter_symbol)
    if observed == expected:
        return True, "variable name %r matches the expected exchange and symbol" % observed
    return False, ("variable name %r does not match the expected %r; the exchange, the "
                   "symbol or the payload family is wrong" % (observed, expected))


def parse_outstanding_share(content, encoding, *, expected_symbol=None,
                            instrument_class="stock"):
    """The auxiliary outstanding-share series -> ordered rows, zeros preserved.

    R2-A. The live bodies are **an array of objects**, not `[date, value]` pairs:

        /*<script>location.href='//sina.com';</script>*/
        var KKE_ShareAmount_sh600011=([{"date":"2001-12-06","amount":14660.5}, ...]);

    Three things follow, and all three were wrong before:

    * the envelope carries an XSS-guard block comment before the assignment. It is
      **parsed as data and never executed**, like every other body here;
    * the entries are objects. The pair form is still accepted, because the plan
      documented it and a vendor may serve either, but a single body must be homogeneous;
    * the vendor names the value field **`amount`**. It is *not* traded amount - it is
      outstanding shares in 万股, the quantity `stock_zh_a_sina.py:207-208` multiplies by
      10,000 and divides volume by. The key is renamed `outstanding_share_wan` here so
      the distinction cannot be lost downstream (G3).

    Zero and non-positive observations are **kept, flagged and reported**, never dropped
    and never repaired: `BJ920000` really does report 0 on 2015-03-06 and 2015-09-15.
    Each row carries `usable`, and an unusable row is excluded only from being used as a
    denominator - see `outstanding_share_as_of`, which never returns one.
    """
    import json

    text = bytes_to_text(content, encoding)
    match = _JSONP_RE.match(text)
    if not match:
        raise DecodeError("the auxiliary body is not a `var NAME = ([...]);` assignment, "
                          "optionally preceded by block comments")
    name, array = match.group(1), match.group(2)
    _scan_trailer(text[match.end():])

    if expected_symbol is not None:
        ok, reason = check_js_variable(name, "outstanding_share", instrument_class,
                                       expected_symbol)
        if not ok:
            raise DecodeError(reason)

    try:
        data = json.loads(array)
    except ValueError:
        # The adapter uses demjson, which tolerates single quotes and unquoted keys. A
        # body strict JSON cannot read is a format change worth reporting, not something
        # to re-parse with looser rules that would hide it.
        raise DecodeError("the auxiliary payload is not strict JSON") from None
    if not isinstance(data, list) or not data:
        raise DecodeError("the auxiliary payload is not a non-empty list")

    shapes = {("object" if isinstance(e, dict) else
               "pair" if isinstance(e, (list, tuple)) and len(e) == 2 else
               "unknown") for e in data}
    if shapes == {"object"}:
        def read(index, entry):
            missing = [k for k in ("date", "amount") if k not in entry]
            if missing:
                raise DecodeError("entry %d is missing %s" % (index, missing))
            return entry["date"], entry["amount"]
    elif shapes == {"pair"}:
        def read(index, entry):
            return entry[0], entry[1]
    else:
        raise DecodeError("the auxiliary entries are not homogeneous objects or "
                          "[date, value] pairs (shapes seen: %s)" % sorted(shapes))

    rows, seen = [], set()
    for index, entry in enumerate(data):
        raw_date, raw_value = read(index, entry)
        date = _normalize_date(raw_date)
        value = _to_number("outstanding_share_wan", raw_value)
        if date in seen:
            raise DecodeError("duplicate date %s in the share series" % date)
        seen.add(date)
        if value < 0:
            # A zero is a real vendor observation and is kept; a NEGATIVE share count is
            # impossible and indicates a corrupt or misparsed body, so it is refused.
            raise DecodeError("entry %d reports a negative share count %r" % (index, value))
        rows.append({"date": date, "outstanding_share_wan": value,
                     "usable": value > 0,
                     "unusable_reason": None if value > 0 else
                                        "the vendor reports zero shares on this date"})
    rows.sort(key=lambda r: r["date"])
    return rows


def share_state_as_of(rows, date):
    """The observation IN FORCE at `date` - usable or not - or `None` before the series.

    The state is the LATEST observation at or before the date. An explicitly reported
    zero is a state, not a gap: it stays in force until a later observation supersedes
    it. Never looks forward.
    """
    state = None
    for row in sorted(rows, key=lambda r: r["date"]):
        if row["date"] > date:
            break
        state = row
    return state


def outstanding_share_as_of(rows, date):
    """The share observation usable as a DENOMINATOR at `date`, or `None`.

    The series is a step function of share-count changes, so the value in force on a date
    is the latest observation at or before it. If that observation is explicitly
    unusable - the vendor reported zero - there is **no usable denominator until a later
    valid observation supersedes it**: an older positive count must not be restored
    across a newer invalid one. This matches the installed adapter's `ffill`, which
    carries an explicit zero forward as zero (`[100, 0, NaN, 200].ffill()` is
    `[100, 0, 0, 200]`, not `[100, 100, 100, 200]`) - an explicit zero and an absent
    observation are different states.

    Never backfills: a date before the first observation returns `None` rather than
    borrowing a later count. The zero itself is preserved in the series and reported by
    `share_series_quality`; it is withheld as a denominator, not discarded as evidence.
    """
    state = share_state_as_of(rows, date)
    if state is None or not state.get("usable"):
        return None
    return state


def invalid_denominator_intervals(rows):
    """Every span in which an explicit unusable observation is in force.

    `[{from, until, reason}]`, `until` being the date of the later valid observation that
    restores a denominator, or `None` when the series ends unusable. Reported so an
    interrupted denominator is visible evidence rather than a silent count of gaps.
    """
    ordered = sorted(rows, key=lambda r: r["date"])
    spans = []
    for index, row in enumerate(ordered):
        if row.get("usable"):
            continue
        later = next((r["date"] for r in ordered[index + 1:] if r.get("usable")), None)
        spans.append({"from": row["date"], "until": later,
                      "reason": row.get("unusable_reason")})
    return spans


def _age_days(row, on_date):
    """Days between a carried-forward observation and the date it is applied to."""
    if not row:
        return None
    return (_dt.date.fromisoformat(on_date)
            - _dt.date.fromisoformat(row["date"])).days


def share_series_quality(rows, window):
    """A reportable summary: coverage relative to the window, and every unusable row."""
    low, high = window
    unusable = [{"date": r["date"], "reason": r["unusable_reason"]}
                for r in rows if not r.get("usable")]
    usable = [r for r in rows if r.get("usable")]
    in_window = [r for r in rows if low <= r["date"] <= high]
    before = [r for r in rows if r["date"] < low]
    first_usable = usable[0]["date"] if usable else None
    return {
        "entries": len(rows),
        "usable_entries": len(usable),
        "unusable_entries": unusable,
        "first_date": rows[0]["date"] if rows else None,
        "last_date": rows[-1]["date"] if rows else None,
        "entries_in_window": len(in_window),
        "entries_before_window": len(before),
        "first_usable_date": first_usable,
        # A step series may legitimately have NO observation inside the window: the value
        # in force is then the last one before it. That is coverage, not absence.
        "value_in_force_at_window_start": (
            outstanding_share_as_of(rows, low) or {}).get("outstanding_share_wan"),
        # A usable DENOMINATOR at the window start. False when the window opens while an
        # explicit zero is in force: coverage cannot bridge an invalid observation.
        "covers_window_start": outstanding_share_as_of(rows, low) is not None,
        # ... and the raw state that decided it, so a withheld zero stays visible.
        "state_at_window_start": share_state_as_of(rows, low),
        "state_at_window_end": share_state_as_of(rows, high),
        "invalid_denominator_intervals": invalid_denominator_intervals(rows),
        # How OLD the carried-forward value is at each end of the window. A step series
        # legitimately has no in-window observation, but a value carried forward for
        # years is weak evidence and must not read as a fresh measurement.
        "carry_in_age_days_at_window_start": _age_days(
            outstanding_share_as_of(rows, low), low),
        "carry_in_age_days_at_window_end": _age_days(
            outstanding_share_as_of(rows, high), high),
        "unit": "wan_shares (万股); multiply by %d for shares" % OUTSTANDING_SHARE_WAN_TO_SHARES,
        "is_traded_amount": False,
    }


# ------------------------------------------------------------------- shape reporting
def key_report(rows, instrument_class):
    """Which required keys are present/absent, and which extra keys the vendor sent."""
    required = STOCK_REQUIRED_KEYS if instrument_class == "stock" else INDEX_REQUIRED_KEYS
    present = {k for r in rows for k in r}
    known = set(required) | set(OPTIONAL_KEYS) | set(INDEX_REQUIRED_KEYS)
    return {"required": list(required),
            "missing": sorted(k for k in required if k not in present),
            "optional_present": sorted(k for k in OPTIONAL_KEYS if k in present),
            "unexpected": sorted(k for k in present if k not in known),
            "amount_present": "amount" in present}
