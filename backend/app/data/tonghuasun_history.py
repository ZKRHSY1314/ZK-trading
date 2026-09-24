"""Pure request and evidence parsing for separately operated M2 history reads.

No transport, configuration discovery, database, provider import or write occurs
here. Callers retain raw bytes even when parsing fails and establish endpoint
identity before authentication. Structural success never verifies price basis,
units, an index alias, historical security identity or dataset eligibility.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
import hashlib
import json
import math
import re
import unicodedata
from typing import Iterable


CHINA = timezone(timedelta(hours=8))
ADJUSTMENTS = {"none": 0, "qfq": 1, "hfq": 2}
FIELDS = ("full_code", "security_name", "open", "high", "low", "latest",
          "transaction_volume", "transaction_amount", "date_time")


class HistoryValidationError(ValueError):
    """A fixed error code and optional row index; never echoes response text."""

    def __init__(self, code: str, row_index: int | None = None):
        self.code = code
        self.row_index = row_index
        super().__init__(code)


def _canonical(symbol: str) -> tuple[str, str, str]:
    if not isinstance(symbol, str):
        raise HistoryValidationError("invalid_canonical_symbol")
    match = re.fullmatch(r"(SH|SZ|BJ)(\d{6})", symbol)
    if match is None:
        raise HistoryValidationError("invalid_canonical_symbol")
    exchange, code = match.groups()
    return symbol, exchange, code


@dataclass(frozen=True)
class SecuritySpec:
    canonical_symbol: str
    instrument_class: str
    response_full_code: str
    host_full_code: str
    mapping_evidence: str = ""

    def __post_init__(self) -> None:
        _, exchange, code = _canonical(self.canonical_symbol)
        if self.instrument_class == "stock":
            market = {"SH": "USHA", "SZ": "USZA", "BJ": "USTM"}[exchange]
            allowed = {"SH": ("USHA", "USHT"), "SZ": ("USZA",), "BJ": ("USTM",)}[exchange]
            if (self.response_full_code != f"{code}.{exchange}"
                    or self.host_full_code not in tuple(prefix + code for prefix in allowed)):
                raise HistoryValidationError("invalid_stock_identity_spec")
            if self.host_full_code != market + code and not self.mapping_evidence.strip():
                raise HistoryValidationError("stock_market_mapping_evidence_required")
        elif self.instrument_class == "benchmark":
            match = re.fullmatch(r"(USHI|USZI)([A-Z0-9]{1,16})", self.host_full_code)
            if match is None:
                raise HistoryValidationError("invalid_benchmark_host_identity")
            suffix = {"USHI": "SH", "USZI": "SZ"}[match.group(1)]
            # The host's public formatter can change an alphanumeric index
            # code (USHI1A0001 has been observed as 10001.SH). Require the
            # separately supplied source identifier, never derive it by
            # removing letters or overwrite the canonical/host identity.
            response = re.fullmatch(r"([A-Z0-9]{1,16})\.(SH|SZ)", self.response_full_code)
            if response is None or response.group(2) != suffix:
                raise HistoryValidationError("inconsistent_benchmark_host_identity")
            if not isinstance(self.mapping_evidence, str) or not self.mapping_evidence.strip():
                raise HistoryValidationError("benchmark_mapping_evidence_required")
        else:
            raise HistoryValidationError("unsupported_instrument_class")

    @classmethod
    def stock(cls, canonical_symbol: str, *, host_full_code: str | None = None,
              mapping_evidence: str = "") -> SecuritySpec:
        _, exchange, code = _canonical(canonical_symbol)
        market = {"SH": "USHA", "SZ": "USZA", "BJ": "USTM"}[exchange]
        return cls(canonical_symbol, "stock", f"{code}.{exchange}",
                   host_full_code or market + code, mapping_evidence)

    @classmethod
    def benchmark(cls, canonical_symbol: str, *, host_full_code: str,
                  response_full_code: str, mapping_evidence: str) -> SecuritySpec:
        # Evidence is recorded, not certified by the existence of this spec.
        return cls(canonical_symbol, "benchmark", response_full_code,
                   host_full_code, mapping_evidence)

    @property
    def host_market_code(self) -> str:
        return self.host_full_code[:4]

    @property
    def response_code(self) -> str:
        return self.response_full_code.rsplit(".", 1)[0]


def _date(value: str) -> date:
    if not isinstance(value, str) or re.fullmatch(r"\d{4}-\d{2}-\d{2}", value) is None:
        raise HistoryValidationError("invalid_contract_date")
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise HistoryValidationError("invalid_contract_date") from None


def _window(start_date: str, end_date: str) -> tuple[date, date]:
    start, end = _date(start_date), _date(end_date)
    if end < start:
        raise HistoryValidationError("reversed_contract_window")
    return start, end


def build_history_request(spec: SecuritySpec, start_date: str, end_date: str,
                          adjustment: str = "none", limit: int = 5000) -> dict:
    start, end = _window(start_date, end_date)
    if adjustment not in ADJUSTMENTS:
        raise HistoryValidationError("invalid_requested_adjustment")
    if type(limit) is not int or not 1 <= limit <= 5000:
        raise HistoryValidationError("invalid_request_limit")
    field = "fullCode" if spec.instrument_class == "stock" else "hostFullCode"
    identifier = spec.response_full_code if field == "fullCode" else spec.host_full_code
    return {
        "market": 1,
        "security": {"market": 1, field: identifier},
        "startTimeUtc": datetime.combine(start, time.min, CHINA).astimezone(
            timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z"),
        "endTimeUtc": datetime.combine(end, time(23, 59, 59, 999000), CHINA).astimezone(
            timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z"),
        "period": 7,
        "adjustment": ADJUSTMENTS[adjustment],
        "limit": limit,
        "fields": list(FIELDS),
    }


def _object(pairs: list[tuple]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise HistoryValidationError("duplicate_json_key")
        result[key] = value
    return result


def _reject_constant(_value: str):
    raise HistoryValidationError("nonfinite_json_constant")


def _number(value, row_index: int, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (str, int, float)):
        raise HistoryValidationError("invalid_" + field, row_index)
    try:
        parsed = float(value)
    except (ValueError, OverflowError):
        raise HistoryValidationError("invalid_" + field, row_index) from None
    if not math.isfinite(parsed):
        raise HistoryValidationError("invalid_" + field, row_index)
    return parsed


def _point_date(value, *, aware: bool = False) -> date:
    if not aware and type(value) is int:
        value = str(value)
    if not isinstance(value, str):
        raise HistoryValidationError("invalid_point_date")
    if not aware and re.fullmatch(r"\d{8}", value):
        value = value[:4] + "-" + value[4:6] + "-" + value[6:]
    if not aware and re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        return _date(value)
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise HistoryValidationError("invalid_point_date") from None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise HistoryValidationError("point_timestamp_timezone_required")
    return parsed.astimezone(CHINA).date()


def _name(value) -> tuple[str | None, str]:
    if value is None or value == "":
        return None, "missing_source_name"
    if not isinstance(value, str):
        return None, "invalid_source_name"
    if not value.strip():
        return None, "missing_source_name"
    if any(unicodedata.category(char).startswith("C") or char == "\ufffd" for char in value):
        return None, "invalid_source_name"
    return value, "source_name_observed"


def parse_history_response(raw: bytes, spec: SecuritySpec, start_date: str,
                           end_date: str, adjustment: str = "none",
                           expected_dates: Iterable[str] | None = None) -> dict:
    """Validate one raw candle response; record coverage without shrinking its domain.

    Missing expected keys are returned as coverage failures. Invalid identities,
    duplicated observations, out-of-window dates or malformed values raise fixed
    errors. The caller must preserve raw bytes on either outcome. No basis/unit
    or mapping eligibility is granted by this parser.
    """
    start, end = _window(start_date, end_date)
    if adjustment not in ADJUSTMENTS:
        raise HistoryValidationError("invalid_requested_adjustment")
    if not isinstance(raw, bytes):
        raise HistoryValidationError("raw_response_bytes_required")
    try:
        body = json.loads(raw.decode("utf-8-sig"), object_pairs_hook=_object,
                          parse_constant=_reject_constant)
    except (UnicodeError, json.JSONDecodeError, RecursionError):
        raise HistoryValidationError("invalid_response_json") from None
    if type(body) is not dict or body.get("ok") is not True:
        raise HistoryValidationError("response_not_ok")
    data = body.get("data")
    if type(data) is not dict:
        raise HistoryValidationError("missing_response_data")
    items = data.get("items")
    if type(items) is not list or len(items) != 1 or type(items[0]) is not dict:
        raise HistoryValidationError("response_requires_single_item")
    item = items[0]
    identity = item.get("security")
    if type(identity) is not dict:
        raise HistoryValidationError("missing_response_identity")
    if (identity.get("fullCode") != spec.response_full_code
            or identity.get("hostFullCode") != spec.host_full_code
            or identity.get("hostMarketCode") != spec.host_market_code
            or type(identity.get("market")) is not int or identity["market"] != 1):
        raise HistoryValidationError("response_identity_mismatch")
    if "code" in identity and identity["code"] != spec.response_code:
        raise HistoryValidationError("response_identity_mismatch")
    reported_adjustment = data.get("adjustment")
    if reported_adjustment is not None:
        if type(reported_adjustment) is not int or reported_adjustment != ADJUSTMENTS[adjustment]:
            raise HistoryValidationError("response_adjustment_mismatch")
    points = item.get("points")
    if type(points) is not list or not points:
        raise HistoryValidationError("empty_or_invalid_points")
    rows, seen, diagnostics = [], set(), []
    item_name, item_name_status = _name(identity.get("name"))
    previous = None
    fields = {"open": "open", "high": "high", "low": "low", "close": "latest",
              "volume": "transaction_volume", "amount": "transaction_amount"}
    for index, point in enumerate(points):
        if type(point) is not dict or type(point.get("values")) is not dict:
            raise HistoryValidationError("invalid_point_shape", index)
        values = point["values"]
        if values.get("full_code") != spec.response_full_code:
            raise HistoryValidationError("point_identity_mismatch", index)
        for key, expected in (("hostFullCode", spec.host_full_code),
                              ("hostMarketCode", spec.host_market_code),
                              ("fullCode", spec.response_full_code),
                              ("code", spec.response_code)):
            if key in values and values[key] != expected:
                raise HistoryValidationError("point_identity_mismatch", index)
        try:
            trade_date = _point_date(values.get("date_time"))
            timestamp_date = _point_date(point.get("timestampUtc"), aware=True)
        except HistoryValidationError as exc:
            raise HistoryValidationError(exc.code, index) from None
        if timestamp_date != trade_date:
            raise HistoryValidationError("timestamp_trade_date_mismatch", index)
        if not start <= trade_date <= end:
            raise HistoryValidationError("point_outside_contract_window", index)
        if trade_date in seen:
            raise HistoryValidationError("duplicate_trade_date", index)
        if previous is not None and trade_date < previous:
            raise HistoryValidationError("unordered_trade_dates", index)
        previous = trade_date
        seen.add(trade_date)
        numbers = {}
        for field, source_field in fields.items():
            value = values.get(source_field)
            if field == "amount" and spec.instrument_class == "benchmark" and value is None:
                numbers[field] = None
            else:
                numbers[field] = _number(value, index, field)
        if any(numbers[field] <= 0 for field in ("open", "high", "low", "close")):
            raise HistoryValidationError("nonpositive_ohlc", index)
        if numbers["volume"] < 0 or (numbers["amount"] is not None and numbers["amount"] < 0):
            raise HistoryValidationError("negative_volume_or_amount", index)
        if (numbers["high"] < max(numbers["open"], numbers["close"], numbers["low"])
                or numbers["low"] > min(numbers["open"], numbers["close"])):
            raise HistoryValidationError("invalid_ohlc_order", index)
        name, name_status = _name(values.get("security_name"))
        if name_status != "source_name_observed":
            diagnostics.append({"row_index": index, "code": name_status})
        rows.append({"date": trade_date.isoformat(), "point_index": index, **numbers,
                     "source_name": name, "raw_security_name": values.get("security_name")})
    expected = None
    if expected_dates is not None:
        if isinstance(expected_dates, (str, bytes)):
            raise HistoryValidationError("invalid_expected_dates")
        expected_list = [_date(value) for value in expected_dates]
        if len(set(expected_list)) != len(expected_list):
            raise HistoryValidationError("duplicate_expected_date")
        if any(not start <= value <= end for value in expected_list):
            raise HistoryValidationError("expected_date_outside_window")
        expected = set(expected_list)
    missing = sorted(expected - seen) if expected is not None else []
    extra = sorted(seen - expected) if expected is not None else []
    return {
        "canonical_symbol": spec.canonical_symbol,
        "instrument_class": spec.instrument_class,
        "response_identity": dict(identity),
        "mapping_evidence": spec.mapping_evidence,
        "mapping_verified": False,
        "rows": rows,
        "raw_sha256": hashlib.sha256(raw).hexdigest(),
        "raw_bytes": len(raw),
        "first_date": rows[0]["date"], "last_date": rows[-1]["date"],
        "requested_adjustment": adjustment,
        "response_adjustment": reported_adjustment,
        "vendor_basis": "unverified", "volume_unit": "unverified", "amount_unit": "unverified",
        "eligible": False,
        "coverage": {"expected_keys_supplied": expected is not None,
                     "expected_count": len(expected) if expected is not None else None,
                     "observed_count": len(rows),
                     "missing_dates": [value.isoformat() for value in missing],
                     "extra_dates": [value.isoformat() for value in extra],
                     "complete": expected is not None and not missing and not extra},
        "item_source_name": item_name,
        "item_name_status": item_name_status,
        "name_diagnostics": diagnostics,
    }
