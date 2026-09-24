"""M2a R1 - the pure decoder. Stored rows come from the captured response bodies.

The defect this closes
----------------------
The previous runner requested the expected URLs, recorded `response.url`, threw the
response BODY away, and then obtained rows from an independent `fetcher(symbol, klass)`
callback. URL equality was treated as proof of origin. It is not: the review made every
simulated response `<html>NOT MARKET DATA</html>`, had the callback return a complete
synthetic grid, and the runner reported `completed`, `promoted=True` and wrote 45,935
rows per view with raw-basis metadata. The unchanged M1 gate passed it, correctly - M1
checks its declared data contract, not whether the ingester told the truth about where
the rows came from. That link was missing here, and this module is the link.

Every row now originates in a captured body. There is no second data path, and the
decoder is pure: bodies in, rows out, no I/O of any kind, so it cannot make an unbudgeted
request even by accident.

Fail closed, always
-------------------
HTML, malformed JSON, a missing or mismatched symbol, an unsupported schema, a missing
basis declaration, empty or malformed rows - each is a rejection carrying a reason, never
a silently empty result and never a default.

Deliberately unimplemented
--------------------------
The real Sina history endpoint returns a JS-encoded payload that needs the vendor's
decode routine and a real sample to validate against. That decoder is NOT written here.
`SINA_KLC_JS` is registered as a KNOWN-UNSUPPORTED format so it fails closed with a clear
reason rather than being guessed at. Building it requires a real response and is out of
scope for an offline milestone.
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import json
import re
from dataclasses import dataclass, field

#: Envelope schema this decoder understands. Anything else is refused.
SUPPORTED_SCHEMA = "m2a.market.v1"
SINA_KLC_JS = "sina.klc_kl.js"

REQUIRED_ROW_FIELDS = ("date", "open", "high", "low", "close")
STOCK_EXTRA_FIELDS = ("volume", "amount")
#: An index reports volume but no traded amount. Requiring it here is what keeps the
#: decoder from silently dropping the column on the way through.
BENCHMARK_EXTRA_FIELDS = ("volume",)
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
SYMBOL_RE = re.compile(r"^(SH|SZ|BJ)\d{6}$")
HTML_HINT = re.compile(r"^\s*(<!doctype|<html|<\?xml)", re.IGNORECASE)


class DecodeError(Exception):
    """The response cannot be trusted to be market data for this security."""


@dataclass
class DecodedResponse:
    symbol: str
    kind: str
    schema: str
    declared_basis: str
    rows: list
    body_sha256: str
    url: str
    byte_length: int
    warnings: list = field(default_factory=list)


def normalize_symbol(raw: str) -> str:
    """One canonical identity. `sz000001`, `SZ000001`, ` sz000001 ` all normalize."""
    text = str(raw or "").strip().upper()
    if not SYMBOL_RE.match(text):
        raise DecodeError("symbol %r is not a supported SH/SZ/BJ identifier" % raw)
    return text


def body_digest(body: str) -> str:
    return hashlib.sha256(body.encode("utf-8", "surrogatepass")).hexdigest()


def decode(body, *, url, expected_symbol, kind):
    """Parse ONE captured response body. Pure: no I/O, no network, no fallback."""
    if body is None:
        raise DecodeError("no response body was captured for %s" % url)
    if not isinstance(body, str):
        raise DecodeError("response body for %s is %s, not text"
                          % (url, type(body).__name__))
    if HTML_HINT.match(body):
        raise DecodeError(
            "response for %s is markup, not market data (starts %r)"
            % (url, body[:40].strip()))

    try:
        payload = json.loads(body)
    except ValueError as exc:
        raise DecodeError("response for %s is not valid JSON: %s" % (url, exc)) from None
    if not isinstance(payload, dict):
        raise DecodeError("response for %s decoded to %s, not an object"
                          % (url, type(payload).__name__))

    schema = str(payload.get("schema") or "")
    if schema == SINA_KLC_JS:
        raise DecodeError(
            "format %r is KNOWN-UNSUPPORTED: the vendor's JS-encoded payload needs its "
            "decode routine and a real sample to validate against, which this offline "
            "milestone does not have. Failing closed rather than guessing." % schema)
    if schema != SUPPORTED_SCHEMA:
        raise DecodeError("unsupported schema %r for %s (expected %r)"
                          % (schema, url, SUPPORTED_SCHEMA))

    want = normalize_symbol(expected_symbol)
    got = payload.get("symbol")
    try:
        got_norm = normalize_symbol(got)
    except DecodeError:
        raise DecodeError("response for %s carries no usable symbol (%r)" % (url, got)) from None
    if got_norm != want:
        raise DecodeError("response for %s is for %s, not the requested %s"
                          % (url, got_norm, want))

    declared_basis = payload.get("basis")
    if declared_basis in (None, ""):
        raise DecodeError("response for %s declares no adjustment basis" % url)
    declared_basis = str(declared_basis).strip()

    raw_rows = payload.get("rows")
    if not isinstance(raw_rows, list) or not raw_rows:
        raise DecodeError("response for %s carries no rows" % url)

    required = REQUIRED_ROW_FIELDS + (STOCK_EXTRA_FIELDS if kind == "stock"
                                      else BENCHMARK_EXTRA_FIELDS)
    rows, seen = [], set()
    for index, row in enumerate(raw_rows):
        if not isinstance(row, dict):
            raise DecodeError("row %d of %s is %s, not an object"
                              % (index, url, type(row).__name__))
        missing = [f for f in required if f not in row]
        if missing:
            raise DecodeError("row %d of %s is missing %s" % (index, url, missing))
        date = str(row["date"]).strip()
        # Shape is not validity: "2025-13-99" matches the pattern and is not a date.
        # This is the same defect class the M1 review found in the D1 gate.
        if not DATE_RE.match(date):
            raise DecodeError("row %d of %s has a malformed date %r" % (index, url, date))
        try:
            _dt.date.fromisoformat(date)
        except ValueError:
            raise DecodeError("row %d of %s has an impossible date %r"
                              % (index, url, date)) from None
        if date in seen:
            raise DecodeError("row %d of %s repeats date %s" % (index, url, date))
        seen.add(date)
        clean = {"date": date}
        for field_name in required[1:]:
            value = row[field_name]
            if value is None:
                clean[field_name] = None
                continue
            try:
                clean[field_name] = float(value)
            except (TypeError, ValueError):
                raise DecodeError("row %d of %s has non-numeric %s=%r"
                                  % (index, url, field_name, value)) from None
        rows.append(clean)

    return DecodedResponse(symbol=want, kind=kind, schema=schema,
                           declared_basis=declared_basis, rows=rows,
                           body_sha256=body_digest(body), url=url,
                           byte_length=len(body))


def merge_stock_responses(history, amount):
    """Combine the two captured stock responses into one row set.

    Both must describe the same security on the same basis. This is a LINEAGE join of two
    parts of one fetch, not corroboration by two independent sources, and it is labelled
    as such wherever it is recorded.
    """
    if history.symbol != amount.symbol:
        raise DecodeError("history is for %s but the amount series is for %s"
                          % (history.symbol, amount.symbol))
    if history.declared_basis != amount.declared_basis:
        raise DecodeError("the two captured responses declare different bases (%r vs %r)"
                          % (history.declared_basis, amount.declared_basis))
    by_date = {r["date"]: r for r in amount.rows}
    extra = sorted(set(by_date) - {r["date"] for r in history.rows})
    if extra:
        raise DecodeError("the amount series carries %d date(s) absent from the price "
                          "history, e.g. %s" % (len(extra), extra[:3]))
    merged = []
    for row in history.rows:
        partner = by_date.get(row["date"])
        if partner is None:
            raise DecodeError("no amount record for %s on %s" % (history.symbol, row["date"]))
        combined = dict(row)
        combined["amount"] = partner.get("amount", row.get("amount"))
        merged.append(combined)
    return merged
