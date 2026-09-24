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
def parse_outstanding_share(content, encoding):
    """`[[date, value], ...]` -> `[{"date": ..., "outstanding_share_wan": ...}]`.

    The adapter names this column `outstanding_share`, multiplies it by 10,000 and uses
    it for `turnover` (`stock_zh_a_sina.py:196-208`). It is NOT traded amount, and it is
    never labelled one here (G3).
    """
    text = bytes_to_text(content, encoding)
    start = text.find("[")
    end = text.rfind("]")
    if start < 0 or end <= start:
        raise DecodeError("no JSON array found in the JSONP body")
    body = text[start:end + 1]
    try:
        import json

        data = json.loads(body)
    except ValueError:
        # The adapter uses demjson (tolerant of single quotes / unquoted keys). A body
        # that strict JSON cannot read is a format change worth reporting, not silently
        # re-parsing with looser rules that would hide it.
        raise DecodeError("the JSONP payload is not strict JSON") from None
    if not isinstance(data, list) or not data:
        raise DecodeError("the JSONP payload is not a non-empty list")

    out = []
    seen = set()
    for index, pair in enumerate(data):
        if not isinstance(pair, (list, tuple)) or len(pair) != 2:
            raise DecodeError("entry %d is not a [date, value] pair" % index)
        date = _normalize_date(pair[0])
        value = _to_number("outstanding_share_wan", pair[1])
        if value <= 0:
            raise DecodeError("entry %d has a non-positive share count %r" % (index, value))
        if date in seen:
            raise DecodeError("duplicate date %s in the share series" % date)
        seen.add(date)
        out.append({"date": date, "outstanding_share_wan": value})
    out.sort(key=lambda r: r["date"])
    return out


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
