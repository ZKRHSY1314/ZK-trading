"""M4-01 pure, causal execution kernel for ONE order decision (contract 0.1.0-draft).

Scope
-----
This module decides whether a single, already-sized order fills at one explicit
execution attempt, and what the exact signed cash / quantity / fee consequences are.
It is deliberately not a backtest service: no portfolio allocation, no stop/exit
priority, no cooldown, no FIFO ledger, no data adapter.  Those are M4-02 / M4-03 and
the interface they need is documented in ``POLICY["portfolio_interface"]`` and in
``claude methods/_m4_20260912/claude_01/CONTRACT.md``.

Design rules (every one of them is checked by ``backend/tests/test_m4_execution.py``):

* Standard library only.  No ``app`` import, no settings, no database, filesystem,
  network, clock or environment access.  The same inputs always give the same
  result and the same ``result_hash``.
* Every temporal fact is a distinct, timezone-aware instant: decision time, the
  availability time of each decision input, order submission, the declared first
  eligible execution point, the expiry derived from an injected ordered exchange
  session calendar, and the actual execution attempt instant.  A prior-close decision
  can only execute from the next session's open onward; a halted session still counts
  toward expiry and settlement.
* Only contemporaneous execution-time evidence can prove a fill.  A price or
  capacity observation must be *observed* no later than the attempt instant and,
  unless it is an explicitly declared model assumption, *available* no later than it.
  A full-day high/low/close/amount is observed at the close and therefore can never
  prove an opening fill.  Missing capacity evidence yields ``unfilled`` with
  ``capacity_unproven`` - never an invented fill.
* Unknown tradability / limit / band / ST / listing state is never treated as normal:
  it is rejected unless the caller declares an explicit, referenced assumption, and
  the result then says which states were assumed.
* Fees are injected, effective-dated, versioned schedules with provenance.  The
  module contains no tariff numbers.  Money arithmetic is ``Decimal`` with declared
  rounding; a rejected or unfilled attempt has zero cash flow and no recorded fill.
* Statuses are distinct: ``rejected`` (the order or its prerequisites are invalid -
  nothing happened), ``unfilled`` (a valid order that did not fill at this attempt
  and stays live until expiry), ``partially_filled`` and ``filled``.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, fields, is_dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import ROUND_CEILING, ROUND_FLOOR, ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Any

CONTRACT_VERSION = "0.1.0-draft"
CONTRACT_NAMESPACE = "m4.execution"

SIDE_BUY = "buy"
SIDE_SELL = "sell"
SIDES = (SIDE_BUY, SIDE_SELL)

PHASE_OPEN_AUCTION = "open_auction"
PHASE_CONTINUOUS = "continuous"
PHASE_CLOSE_AUCTION = "close_auction"
PHASES = (PHASE_OPEN_AUCTION, PHASE_CONTINUOUS, PHASE_CLOSE_AUCTION)

STATUS_REJECTED = "rejected"
STATUS_UNFILLED = "unfilled"
STATUS_PARTIAL = "partially_filled"
STATUS_FILLED = "filled"
STATUSES = (STATUS_REJECTED, STATUS_UNFILLED, STATUS_PARTIAL, STATUS_FILLED)

ROLE_STOCK = "stock"
ROLES = (ROLE_STOCK, "benchmark", "index", "fund", "other")

EVIDENCE_CONTEMPORANEOUS = "contemporaneous"
EVIDENCE_ASSUMPTION = "predeclared_assumption"
EVIDENCE_KINDS = (EVIDENCE_CONTEMPORANEOUS, EVIDENCE_ASSUMPTION)

TRADABILITY_STATUSES = ("tradable", "suspended", "unknown")
LIMIT_STATES = ("none", "limit_up", "limit_down", "unknown")
BAND_STATES = ("band", "no_band", "unknown")
ST_STATUSES = ("st", "not_st", "unknown")
LISTING_STATES = ("seasoned", "new_listing", "unknown")
ASSUMABLE_STATES = ("limit_state", "band_state", "st_status", "listing_state")

ODD_LOT_RULES = ("whole_odd_remainder_only", "any", "forbidden")
FEE_PROVENANCES = ("hypothetical_fixture", "sourced_verified")
CAPACITY_UNITS = ("share", "CNY")

MONEY_QUANTUM = Decimal("0.01")
MAX_RATE = Decimal("0.5")
MAX_SLIPPAGE = Decimal("0.1")
MAX_MONEY = Decimal("1e15")
MAX_QUANTITY = 10**12

# Reason codes.  ``rejected`` codes mean the order or its prerequisites are invalid and
# nothing happened; ``unfilled`` codes mean a valid order did not fill at this attempt.
REJECT_CODES = (
    "invalid_input", "symbol_mismatch", "side_mismatch", "decision_id_mismatch", "non_tradable_role",
    "calendar_mismatch", "evidence_without_provenance", "input_not_available_at_decision",
    "decision_session_not_in_calendar", "decision_before_session_close", "decision_after_next_session_open",
    "next_session_beyond_calendar", "submitted_before_decision", "submitted_after_eligible",
    "eligible_from_not_in_session", "eligible_before_next_session_open", "expiry_beyond_calendar",
    "execution_outside_session", "attempt_session_mismatch", "execution_before_eligible", "order_expired", "execution_phase_mismatch",
    "evidence_session_mismatch", "evidence_observed_after_execution", "evidence_available_after_execution",
    "account_state_after_execution", "tradability_unknown", "unknown_state", "band_prices_missing",
    "band_prices_invalid", "limit_price_outside_band", "price_not_tick_aligned", "quantity_not_in_lot_policy",
    "odd_lot_rule_violation", "fee_schedule_not_applicable", "insufficient_cash", "insufficient_settled_inventory",
    "negative_cash_after_fees",
)
UNFILLED_CODES = (
    "suspended", "limit_up_no_buy_fill", "limit_down_no_sell_fill", "fill_price_exceeds_limit_price",
    "fill_price_below_limit_price", "capacity_unproven", "capacity_exhausted", "capacity_below_minimum_lot",
)


class ExecutionInputError(ValueError):
    """Malformed input.  ``execute`` converts it into a ``rejected`` result."""

    def __init__(self, code: str, detail: str) -> None:
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail


# --------------------------------------------------------------------------------------
# canonical serialization and identities
# --------------------------------------------------------------------------------------

def _canonical_default(value: Any) -> Any:
    if isinstance(value, Decimal):
        if not value.is_finite():
            raise ExecutionInputError("invalid_input", "non-finite Decimal cannot be serialized")
        return str(value)
    if is_dataclass(value) and not isinstance(value, type):
        return {f.name: getattr(value, f.name) for f in fields(value)}
    if isinstance(value, (set, frozenset)):
        return sorted(value)
    raise ExecutionInputError("invalid_input", f"unserializable value of type {type(value).__name__}")


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False,
                      default=_canonical_default)


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# --------------------------------------------------------------------------------------
# scalar validation
# --------------------------------------------------------------------------------------

def _is_bool(value: Any) -> bool:
    return isinstance(value, bool)


def _require_str(value: Any, code: str, what: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ExecutionInputError(code, f"{what} must be a non-empty string, got {value!r}")
    return value


def _require_bool(value: Any, code: str, what: str) -> bool:
    if not _is_bool(value):
        raise ExecutionInputError(code, f"{what} must be bool, got {value!r}")
    return value


def _require_choice(value: Any, choices: tuple[str, ...], code: str, what: str) -> str:
    if value not in choices:
        raise ExecutionInputError(code, f"{what} must be one of {choices}, got {value!r}")
    return value


def _decimal(value: Any, code: str, what: str) -> Decimal:
    """Accept Decimal, int or a decimal string.  Floats and bools are refused: a float
    carries binary error into money and NaN/inf are not values."""
    if _is_bool(value) or isinstance(value, float):
        raise ExecutionInputError(code, f"{what} must be Decimal, int or decimal string (not float/bool), got {value!r}")
    if isinstance(value, Decimal):
        d = value
    elif isinstance(value, int):
        d = Decimal(value)
    elif isinstance(value, str):
        try:
            d = Decimal(value.strip())
        except (InvalidOperation, ValueError) as exc:
            raise ExecutionInputError(code, f"{what} is not a decimal string: {value!r}") from exc
    else:
        raise ExecutionInputError(code, f"{what} has unsupported type {type(value).__name__}")
    if not d.is_finite():
        raise ExecutionInputError(code, f"{what} must be finite, got {value!r}")
    return d


def _money(value: Any, code: str, what: str, *, allow_zero: bool = False, cents: bool = False) -> Decimal:
    d = _decimal(value, code, what)
    if d < 0 or (d == 0 and not allow_zero):
        raise ExecutionInputError(code, f"{what} must be {'>= 0' if allow_zero else '> 0'}, got {d}")
    if d > MAX_MONEY:
        raise ExecutionInputError(code, f"{what} exceeds bound {MAX_MONEY}")
    if cents and d != d.quantize(MONEY_QUANTUM):
        raise ExecutionInputError(code, f"{what} must not carry more than 2 decimals, got {d}")
    return d


NUMERIC_FIELDS = frozenset({"limit_price", "price", "quantity", "limit_up_price", "limit_down_price", "available_cash",
                            "buy_commission_rate", "sell_commission_rate", "min_commission", "transfer_fee_rate",
                            "sell_stamp_duty_rate", "slippage_rate", "max_participation_rate", "tick_size"})


def _norm_num(value: Any) -> str:
    return format(_decimal(value, "invalid_input", "numeric field").normalize(), "f")


def _record(value: Any) -> Any:
    """Canonical primitive record of an input: numeric spellings are normalized so that
    Decimal('10.10') and '10.1' bind the same identity; everything else is literal."""
    if is_dataclass(value) and not isinstance(value, type):
        out = {}
        for f in fields(value):
            v = getattr(value, f.name)
            if f.name in NUMERIC_FIELDS and isinstance(v, (Decimal, str)):
                out[f.name] = _norm_num(v)
            else:
                out[f.name] = _record(v)
        return out
    if isinstance(value, (tuple, list)):
        return [_record(v) for v in value]
    if isinstance(value, dict):
        return {k: _record(v) for k, v in value.items()}
    return value


def _rate(value: Any, code: str, what: str, *, maximum: Decimal = MAX_RATE, minimum: Decimal = Decimal(0)) -> Decimal:
    d = _decimal(value, code, what)
    if d < minimum or d > maximum:
        raise ExecutionInputError(code, f"{what} must be within [{minimum}, {maximum}], got {d}")
    return d


def _quantity(value: Any, code: str, what: str, *, minimum: int = 0, maximum: int = MAX_QUANTITY) -> int:
    if _is_bool(value) or not isinstance(value, int):
        raise ExecutionInputError(code, f"{what} must be int, got {value!r}")
    if value < minimum or value > maximum:
        raise ExecutionInputError(code, f"{what} must be within [{minimum}, {maximum}], got {value}")
    return value


def _instant(value: Any, code: str, what: str) -> datetime:
    """Timezone-aware ISO-8601 instant.  Naive strings are refused."""
    if not isinstance(value, str) or not value.strip():
        raise ExecutionInputError(code, f"{what} must be an ISO-8601 string, got {value!r}")
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(text)
    except ValueError as exc:
        raise ExecutionInputError(code, f"{what} is not ISO-8601: {value!r}") from exc
    if dt.tzinfo is None or dt.utcoffset() is None:
        raise ExecutionInputError(code, f"{what} must be timezone-aware: {value!r}")
    return dt


def _session_date(value: Any, code: str, what: str) -> date:
    if not isinstance(value, str) or len(value) != 10:
        raise ExecutionInputError(code, f"{what} must be YYYY-MM-DD, got {value!r}")
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ExecutionInputError(code, f"{what} is not a date: {value!r}") from exc


def _hhmm(value: Any, code: str, what: str) -> tuple[int, int]:
    if not isinstance(value, str) or len(value) != 5 or value[2] != ":":
        raise ExecutionInputError(code, f"{what} must be HH:MM, got {value!r}")
    try:
        h, m = int(value[:2]), int(value[3:])
    except ValueError as exc:
        raise ExecutionInputError(code, f"{what} must be HH:MM, got {value!r}") from exc
    if not (0 <= h < 24 and 0 <= m < 60):
        raise ExecutionInputError(code, f"{what} out of range: {value!r}")
    return h, m


def _tz(value: Any, code: str) -> timezone:
    if not isinstance(value, str) or len(value) != 6 or value[0] not in "+-" or value[3] != ":":
        raise ExecutionInputError(code, f"tz_offset must look like +08:00, got {value!r}")
    try:
        hours, minutes = int(value[1:3]), int(value[4:6])
    except ValueError as exc:
        raise ExecutionInputError(code, f"tz_offset must look like +08:00, got {value!r}") from exc
    delta = timedelta(hours=hours, minutes=minutes)
    return timezone(-delta if value[0] == "-" else delta)


def quantize_money(value: Decimal) -> Decimal:
    return value.quantize(MONEY_QUANTUM, rounding=ROUND_HALF_UP)


def round_to_tick(price: Decimal, tick: Decimal, direction: str) -> Decimal:
    steps = price / tick
    rounding = ROUND_CEILING if direction == "up" else ROUND_FLOOR
    n = steps.to_integral_value(rounding=rounding)
    return (n * tick).quantize(tick)


def is_tick_aligned(price: Decimal, tick: Decimal) -> bool:
    steps = price / tick
    return steps == steps.to_integral_value()


# --------------------------------------------------------------------------------------
# input dataclasses (all frozen; ``validated()`` raises ExecutionInputError)
# --------------------------------------------------------------------------------------

@dataclass(frozen=True)
class SessionCalendar:
    """Injected, ordered exchange sessions with the session clock.  Never inferred from
    prices.  ``halted_sessions`` are exchange sessions that were halted for the market or
    the venue; they stay in the ordered list so expiry and settlement keep counting them
    (the kernel reports them, it never drops them)."""

    sessions: tuple[str, ...]
    tz_offset: str
    open_time: str
    close_time: str
    source_ref: str
    available_at: str
    synthetic: bool
    halted_sessions: tuple[str, ...] = ()

    def validated(self) -> "SessionCalendar":
        code = "invalid_input"
        if not isinstance(self.sessions, tuple) or not self.sessions:
            raise ExecutionInputError(code, "calendar sessions must be a non-empty tuple")
        previous: date | None = None
        for s in self.sessions:
            d = _session_date(s, code, "calendar session")
            if previous is not None and d <= previous:
                raise ExecutionInputError(code, f"calendar sessions must be strictly increasing and unique at {s}")
            previous = d
        _tz(self.tz_offset, code)
        o, c = _hhmm(self.open_time, code, "open_time"), _hhmm(self.close_time, code, "close_time")
        if o >= c:
            raise ExecutionInputError(code, "open_time must precede close_time")
        _require_str(self.source_ref, code, "calendar source_ref")
        _instant(self.available_at, code, "calendar available_at")
        _require_bool(self.synthetic, code, "calendar synthetic")
        if not isinstance(self.halted_sessions, tuple):
            raise ExecutionInputError(code, "halted_sessions must be a tuple")
        index = self.index()
        seen: set[str] = set()
        for h in self.halted_sessions:
            if h not in index:
                raise ExecutionInputError(code, f"halted session {h} is not a calendar session")
            if h in seen:
                raise ExecutionInputError(code, f"halted session {h} duplicated")
            seen.add(h)
        return self

    def tzinfo(self) -> timezone:
        return _tz(self.tz_offset, "invalid_input")

    def index(self) -> dict[str, int]:
        return {s: i for i, s in enumerate(self.sessions)}

    def _at(self, session: str, hhmm: str) -> datetime:
        h, m = _hhmm(hhmm, "invalid_input", "time")
        return datetime.combine(date.fromisoformat(session), datetime.min.time(), self.tzinfo()).replace(hour=h, minute=m)

    def open_at(self, session: str) -> datetime:
        return self._at(session, self.open_time)

    def close_at(self, session: str) -> datetime:
        return self._at(session, self.close_time)

    def local_date(self, instant: datetime) -> str:
        return instant.astimezone(self.tzinfo()).date().isoformat()

    def prefix(self, through_session: str) -> tuple[str, ...]:
        return self.sessions[: self.index()[through_session] + 1]

    def fingerprint(self) -> str:
        return sha256_text(canonical_json({"sessions": list(self.sessions), "tz_offset": self.tz_offset,
                                           "open_time": self.open_time, "close_time": self.close_time}))

    def prefix_record(self, through_session: str) -> dict[str, Any]:
        """Only the consumed prefix binds a result: a changed future suffix cannot alter
        an earlier decision's identity."""
        prefix = self.prefix(through_session)
        halted = [h for h in self.halted_sessions if h in prefix]
        return {"prefix_fingerprint": sha256_text(canonical_json({"sessions": list(prefix), "tz_offset": self.tz_offset,
                                                                  "open_time": self.open_time, "close_time": self.close_time,
                                                                  "halted_sessions": halted})),
                "prefix_sessions": len(prefix), "first": prefix[0], "last": prefix[-1], "halted_in_prefix": halted,
                "tz_offset": self.tz_offset, "open_time": self.open_time, "close_time": self.close_time,
                "source_ref": self.source_ref, "available_at": self.available_at, "synthetic": self.synthetic}


@dataclass(frozen=True)
class InputAvailability:
    """One input the decision consumed and the instant it became available."""

    name: str
    available_at: str
    source_ref: str

    def validated(self) -> "InputAvailability":
        _require_str(self.name, "invalid_input", "decision input name")
        _instant(self.available_at, "invalid_input", f"input {self.name} available_at")
        _require_str(self.source_ref, "evidence_without_provenance", f"input {self.name} source_ref")
        return self


@dataclass(frozen=True)
class Decision:
    """A prior-close decision: it used ``decision_session``'s close and was taken at
    ``decided_at`` (after that close, before the next session opens)."""

    decision_id: str
    symbol: str
    side: str
    decision_session: str
    decided_at: str
    inputs: tuple[InputAvailability, ...]
    basis_ref: str

    def validated(self) -> "Decision":
        code = "invalid_input"
        _require_str(self.decision_id, code, "decision_id")
        _require_str(self.symbol, code, "decision symbol")
        _require_choice(self.side, SIDES, code, "decision side")
        _session_date(self.decision_session, code, "decision_session")
        _instant(self.decided_at, code, "decided_at")
        if not isinstance(self.inputs, tuple) or not self.inputs:
            raise ExecutionInputError(code, "decision inputs must be a non-empty tuple")
        names: set[str] = set()
        for item in self.inputs:
            if not isinstance(item, InputAvailability):
                raise ExecutionInputError(code, "decision inputs must be InputAvailability")
            item.validated()
            if item.name in names:
                raise ExecutionInputError(code, f"duplicate decision input {item.name}")
            names.add(item.name)
        _require_str(self.basis_ref, "evidence_without_provenance", "decision basis_ref")
        return self


@dataclass(frozen=True)
class Order:
    order_id: str
    decision_id: str
    symbol: str
    side: str
    quantity: int
    limit_price: Any
    submitted_at: str
    eligible_from: str
    expiry_sessions: int
    execution_phase: str

    def validated(self) -> "Order":
        code = "invalid_input"
        _require_str(self.order_id, code, "order_id")
        _require_str(self.decision_id, code, "order decision_id")
        _require_str(self.symbol, code, "order symbol")
        _require_choice(self.side, SIDES, code, "order side")
        _quantity(self.quantity, code, "order quantity", minimum=1)
        _money(self.limit_price, code, "order limit_price")
        _instant(self.submitted_at, code, "submitted_at")
        _instant(self.eligible_from, code, "eligible_from")
        _quantity(self.expiry_sessions, code, "expiry_sessions", minimum=1, maximum=250)
        _require_choice(self.execution_phase, PHASES, code, "execution_phase")
        return self

    def limit(self) -> Decimal:
        return _money(self.limit_price, "invalid_input", "order limit_price")


@dataclass(frozen=True)
class Instrument:
    """Identity and role of the traded security.  ``board`` is declared evidence (with a
    reference), not inferred from the code prefix; ``calendar_ref`` names the session
    calendar (its ``source_ref``) the instrument trades on."""

    symbol: str
    role: str
    board: str
    listing_evidence_ref: str
    calendar_ref: str
    synthetic: bool

    def validated(self) -> "Instrument":
        code = "invalid_input"
        _require_str(self.symbol, code, "instrument symbol")
        _require_choice(self.role, ROLES, code, "instrument role")
        _require_str(self.board, code, "instrument board")
        _require_str(self.listing_evidence_ref, "evidence_without_provenance", "instrument listing_evidence_ref")
        _require_str(self.calendar_ref, code, "instrument calendar_ref")
        _require_bool(self.synthetic, code, "instrument synthetic")
        return self


@dataclass(frozen=True)
class TradabilityEvidence:
    symbol: str
    session: str
    status: str
    limit_state: str
    band_state: str
    limit_up_price: Any
    limit_down_price: Any
    st_status: str
    listing_state: str
    observed_at: str
    available_at: str
    source_ref: str
    synthetic: bool

    def validated(self) -> "TradabilityEvidence":
        code = "invalid_input"
        _require_str(self.symbol, code, "tradability symbol")
        _session_date(self.session, code, "tradability session")
        _require_choice(self.status, TRADABILITY_STATUSES, code, "tradability status")
        _require_choice(self.limit_state, LIMIT_STATES, code, "limit_state")
        _require_choice(self.band_state, BAND_STATES, code, "band_state")
        if self.limit_up_price is not None:
            _money(self.limit_up_price, code, "limit_up_price")
        if self.limit_down_price is not None:
            _money(self.limit_down_price, code, "limit_down_price")
        _require_choice(self.st_status, ST_STATUSES, code, "st_status")
        _require_choice(self.listing_state, LISTING_STATES, code, "listing_state")
        _instant(self.observed_at, code, "tradability observed_at")
        _instant(self.available_at, code, "tradability available_at")
        _require_str(self.source_ref, "evidence_without_provenance", "tradability source_ref")
        _require_bool(self.synthetic, code, "tradability synthetic")
        return self


@dataclass(frozen=True)
class PriceObservation:
    """An execution-time price print.  ``kind`` says whether it was contemporaneously
    available (``available_at`` <= attempt instant is then required) or is a declared
    model assumption (e.g. 'the daily-bar open equals the 09:30 auction print'), which
    must carry ``assumption_ref`` and downgrades the result's evidence grade."""

    symbol: str
    price: Any
    field: str
    observed_at: str
    available_at: str
    source_ref: str
    kind: str
    synthetic: bool
    assumption_ref: str | None = None

    def validated(self) -> "PriceObservation":
        code = "invalid_input"
        _require_str(self.symbol, code, "price symbol")
        _money(self.price, code, "observed price")
        _require_str(self.field, code, "price field")
        _instant(self.observed_at, code, "price observed_at")
        _instant(self.available_at, code, "price available_at")
        _require_str(self.source_ref, "evidence_without_provenance", "price source_ref")
        _require_choice(self.kind, EVIDENCE_KINDS, code, "price kind")
        _require_bool(self.synthetic, code, "price synthetic")
        if self.kind == EVIDENCE_ASSUMPTION:
            _require_str(self.assumption_ref, "evidence_without_provenance", "price assumption_ref")
        elif self.assumption_ref is not None:
            raise ExecutionInputError(code, "contemporaneous price must not carry assumption_ref")
        return self


@dataclass(frozen=True)
class LiquidityCapacity:
    """Executable capacity evidence for the attempt's phase, in shares or CNY, with the
    instant it was observed and became available, and how much of it earlier fills of
    the same actor already consumed (cumulative contract)."""

    symbol: str
    capacity_id: str
    quantity: Any
    unit: str
    basis: str
    observed_at: str
    available_at: str
    source_ref: str
    kind: str
    synthetic: bool
    consumed_quantity: int = 0
    assumption_ref: str | None = None

    def validated(self) -> "LiquidityCapacity":
        code = "invalid_input"
        _require_str(self.symbol, code, "capacity symbol")
        _require_str(self.capacity_id, code, "capacity_id")
        _require_choice(self.unit, CAPACITY_UNITS, code, "capacity unit")
        if self.unit == "share":
            _quantity(self.quantity, code, "capacity quantity", minimum=0)
        else:
            _money(self.quantity, code, "capacity amount", allow_zero=True)
        _require_str(self.basis, code, "capacity basis")
        _instant(self.observed_at, code, "capacity observed_at")
        _instant(self.available_at, code, "capacity available_at")
        _require_str(self.source_ref, "evidence_without_provenance", "capacity source_ref")
        _require_choice(self.kind, EVIDENCE_KINDS, code, "capacity kind")
        _require_bool(self.synthetic, code, "capacity synthetic")
        _quantity(self.consumed_quantity, code, "consumed_quantity", minimum=0)
        if self.kind == EVIDENCE_ASSUMPTION:
            _require_str(self.assumption_ref, "evidence_without_provenance", "capacity assumption_ref")
        elif self.assumption_ref is not None:
            raise ExecutionInputError(code, "contemporaneous capacity must not carry assumption_ref")
        return self


@dataclass(frozen=True)
class InventoryLot:
    quantity: int
    acquired_session: str

    def validated(self) -> "InventoryLot":
        _quantity(self.quantity, "invalid_input", "inventory lot quantity", minimum=1)
        _session_date(self.acquired_session, "invalid_input", "inventory acquired_session")
        return self


@dataclass(frozen=True)
class AccountState:
    """Simulated account state as of an instant: available cash and inventory lots with
    the session each was acquired in.  Never a real account."""

    account_ref: str
    available_cash: Any
    inventory: tuple[InventoryLot, ...]
    as_of: str
    synthetic: bool

    def validated(self) -> "AccountState":
        code = "invalid_input"
        _require_str(self.account_ref, code, "account_ref")
        _money(self.available_cash, code, "available_cash", allow_zero=True, cents=True)
        if not isinstance(self.inventory, tuple):
            raise ExecutionInputError(code, "inventory must be a tuple")
        for lot in self.inventory:
            if not isinstance(lot, InventoryLot):
                raise ExecutionInputError(code, "inventory lots must be InventoryLot")
            lot.validated()
        _instant(self.as_of, code, "account as_of")
        _require_bool(self.synthetic, code, "account synthetic")
        return self

    def cash(self) -> Decimal:
        return _money(self.available_cash, "invalid_input", "available_cash", allow_zero=True)


@dataclass(frozen=True)
class FeeSchedule:
    """Injected, effective-dated, versioned fee assumptions.  The kernel has no default
    rates; a schedule's ``provenance`` states whether it is a hypothetical fixture or a
    sourced, verified tariff (which additionally needs ``verification_ref``)."""

    schedule_id: str
    version: str
    provenance: str
    source_ref: str
    effective_from: str
    effective_to: str | None
    applies_to_boards: tuple[str, ...]
    buy_commission_rate: Any
    sell_commission_rate: Any
    min_commission: Any
    transfer_fee_rate: Any
    sell_stamp_duty_rate: Any
    currency: str = "CNY"
    rounding: str = "ROUND_HALF_UP_0.01_per_charge"
    verification_ref: str | None = None

    def validated(self) -> "FeeSchedule":
        code = "invalid_input"
        _require_str(self.schedule_id, code, "schedule_id")
        _require_str(self.version, code, "fee schedule version")
        _require_choice(self.provenance, FEE_PROVENANCES, code, "fee provenance")
        _require_str(self.source_ref, "evidence_without_provenance", "fee schedule source_ref")
        if self.provenance == "sourced_verified":
            _require_str(self.verification_ref, "evidence_without_provenance", "sourced fee schedule verification_ref")
        start = _session_date(self.effective_from, code, "effective_from")
        if self.effective_to is not None and _session_date(self.effective_to, code, "effective_to") < start:
            raise ExecutionInputError(code, "effective_to precedes effective_from")
        if not isinstance(self.applies_to_boards, tuple) or not self.applies_to_boards:
            raise ExecutionInputError(code, "applies_to_boards must be a non-empty tuple")
        for b in self.applies_to_boards:
            _require_str(b, code, "applies_to_boards entry")
        _rate(self.buy_commission_rate, code, "buy_commission_rate")
        _rate(self.sell_commission_rate, code, "sell_commission_rate")
        _money(self.min_commission, code, "min_commission", allow_zero=True, cents=True)
        _rate(self.transfer_fee_rate, code, "transfer_fee_rate")
        _rate(self.sell_stamp_duty_rate, code, "sell_stamp_duty_rate")
        if self.currency != "CNY":
            raise ExecutionInputError(code, "only CNY schedules are modelled in this contract")
        if self.rounding != "ROUND_HALF_UP_0.01_per_charge":
            raise ExecutionInputError(code, "unsupported fee rounding declaration")
        return self

    def applies(self, session: str, board: str) -> tuple[bool, str]:
        d = date.fromisoformat(session)
        if d < date.fromisoformat(self.effective_from):
            return False, f"session {session} precedes effective_from {self.effective_from}"
        if self.effective_to is not None and d > date.fromisoformat(self.effective_to):
            return False, f"session {session} is after effective_to {self.effective_to}"
        if "*" not in self.applies_to_boards and board not in self.applies_to_boards:
            return False, f"board {board} not in {self.applies_to_boards}"
        return True, "applicable"


@dataclass(frozen=True)
class LotPolicy:
    """Declared per venue/board; the kernel does not assume one rule fits every exchange."""

    policy_id: str
    min_buy_quantity: int
    buy_increment: int
    sell_increment: int
    odd_lot_sell_rule: str
    max_order_quantity: int

    def validated(self) -> "LotPolicy":
        code = "invalid_input"
        _require_str(self.policy_id, code, "lot policy_id")
        _quantity(self.min_buy_quantity, code, "min_buy_quantity", minimum=1)
        _quantity(self.buy_increment, code, "buy_increment", minimum=1)
        _quantity(self.sell_increment, code, "sell_increment", minimum=1)
        _require_choice(self.odd_lot_sell_rule, ODD_LOT_RULES, code, "odd_lot_sell_rule")
        _quantity(self.max_order_quantity, code, "max_order_quantity", minimum=1)
        if self.min_buy_quantity % self.buy_increment:
            raise ExecutionInputError(code, "min_buy_quantity must be a multiple of buy_increment")
        return self


@dataclass(frozen=True)
class SettlementPolicy:
    policy_id: str
    sellable_after_sessions: int
    counts_halted_sessions: bool = True

    def validated(self) -> "SettlementPolicy":
        code = "invalid_input"
        _require_str(self.policy_id, code, "settlement policy_id")
        _quantity(self.sellable_after_sessions, code, "sellable_after_sessions", minimum=0, maximum=10)
        if self.counts_halted_sessions is not True:
            raise ExecutionInputError(code, "halted sessions must count toward settlement (counts_halted_sessions=True)")
        return self


@dataclass(frozen=True)
class ExecutionAssumptions:
    """Predeclared model assumptions with provenance: adverse slippage, participation cap,
    tick, lot and settlement policies, and explicit values to assume when tradability
    evidence reports a state as unknown (otherwise unknown is rejected)."""

    assumption_id: str
    provenance: str
    source_ref: str
    slippage_rate: Any
    max_participation_rate: Any
    tick_size: Any
    lot_policy: LotPolicy
    settlement_policy: SettlementPolicy
    unknown_state_assumptions: tuple[tuple[str, str], ...] = ()

    def validated(self) -> "ExecutionAssumptions":
        code = "invalid_input"
        _require_str(self.assumption_id, code, "assumption_id")
        _require_choice(self.provenance, FEE_PROVENANCES, code, "assumptions provenance")
        _require_str(self.source_ref, "evidence_without_provenance", "assumptions source_ref")
        _rate(self.slippage_rate, code, "slippage_rate", maximum=MAX_SLIPPAGE)
        _rate(self.max_participation_rate, code, "max_participation_rate", maximum=Decimal(1), minimum=Decimal("0.000001"))
        _money(self.tick_size, code, "tick_size")
        if not isinstance(self.lot_policy, LotPolicy) or not isinstance(self.settlement_policy, SettlementPolicy):
            raise ExecutionInputError(code, "lot_policy / settlement_policy types")
        self.lot_policy.validated()
        self.settlement_policy.validated()
        if not isinstance(self.unknown_state_assumptions, tuple):
            raise ExecutionInputError(code, "unknown_state_assumptions must be a tuple of (field, value)")
        seen: set[str] = set()
        for item in self.unknown_state_assumptions:
            if not (isinstance(item, tuple) and len(item) == 2):
                raise ExecutionInputError(code, "unknown_state_assumptions entries must be (field, value)")
            fld, val = item
            _require_choice(fld, ASSUMABLE_STATES, code, "assumed state field")
            choices = {"limit_state": LIMIT_STATES, "band_state": BAND_STATES, "st_status": ST_STATUSES, "listing_state": LISTING_STATES}[fld]
            if val not in choices or val == "unknown":
                raise ExecutionInputError(code, f"assumed value for {fld} must be a known value, got {val!r}")
            if fld in seen:
                raise ExecutionInputError(code, f"duplicate assumption for {fld}")
            seen.add(fld)
        return self

    def assumed(self) -> dict[str, str]:
        return dict(self.unknown_state_assumptions)


@dataclass(frozen=True)
class ExecutionAttempt:
    """The single instant at which the adapter asks whether the live order fills."""

    attempt_id: str
    executed_at: str
    session: str
    phase: str

    def validated(self) -> "ExecutionAttempt":
        code = "invalid_input"
        _require_str(self.attempt_id, code, "attempt_id")
        _instant(self.executed_at, code, "executed_at")
        _session_date(self.session, code, "attempt session")
        _require_choice(self.phase, PHASES, code, "attempt phase")
        return self


@dataclass(frozen=True)
class ExecutionRequest:
    decision: Decision
    order: Order
    instrument: Instrument
    calendar: SessionCalendar
    tradability: TradabilityEvidence
    price: PriceObservation
    account: AccountState
    fee_schedule: FeeSchedule
    assumptions: ExecutionAssumptions
    attempt: ExecutionAttempt
    capacity: LiquidityCapacity | None = None

    def validated(self) -> "ExecutionRequest":
        for name in ("decision", "order", "instrument", "calendar", "tradability", "price", "account", "fee_schedule",
                     "assumptions", "attempt"):
            value = getattr(self, name)
            if not hasattr(value, "validated"):
                raise ExecutionInputError("invalid_input", f"{name} has unsupported type {type(value).__name__}")
            value.validated()
        if self.capacity is not None:
            if not isinstance(self.capacity, LiquidityCapacity):
                raise ExecutionInputError("invalid_input", "capacity must be LiquidityCapacity or None")
            self.capacity.validated()
        return self

    def is_synthetic(self) -> bool:
        return any([self.instrument.synthetic, self.calendar.synthetic, self.tradability.synthetic, self.price.synthetic,
                    self.account.synthetic, self.capacity.synthetic if self.capacity is not None else False])


# --------------------------------------------------------------------------------------
# policy record (canonical; hash is the contract identity)
# --------------------------------------------------------------------------------------

_POLICY_SOURCE: dict[str, Any] = {
    "namespace": CONTRACT_NAMESPACE,
    "contract_version": CONTRACT_VERSION,
    "scope": "one already-sized order, one execution attempt; no portfolio, ledger, adapter, clock or I/O",
    "temporal_chain": [
        "every decision input available_at <= decided_at",
        "close(decision_session) <= decided_at < open(next_session)  (prior-close decision)",
        "decided_at <= submitted_at <= eligible_from",
        "eligible_from >= open(next_session) and eligible_from within its own session [open, close]",
        "expiry_session = sessions[index(eligible_session) + expiry_sessions - 1]; expires_at = close(expiry_session); halted sessions are counted",
        "eligible_from <= executed_at <= expires_at; executed_at within a calendar session [open, close]",
        "open_auction: executed_at == open; continuous: open < executed_at < close; close_auction: executed_at == close",
        "tradability.session == attempt.session; evidence observed_at <= executed_at; contemporaneous evidence available_at <= executed_at",
        "price/capacity observation local date == attempt session; account.as_of <= executed_at",
    ],
    "evidence": {
        "kinds": list(EVIDENCE_KINDS),
        "assumption_needs_ref": True,
        "full_day_fields": "observed at the close, so they cannot prove an opening fill (observed_after_execution)",
        "missing_capacity": "unfilled:capacity_unproven (never an invented fill)",
        "unknown_states": "rejected unless an explicit unknown_state_assumption is declared; assumed states are reported",
        "declared_symbol_or_date": "not market evidence; every evidence object carries source_ref",
    },
    "tradability": {
        "suspended": "unfilled:suspended (order stays live; expiry keeps counting)",
        "limit_up": "buy unfilled:limit_up_no_buy_fill; sell may fill",
        "limit_down": "sell unfilled:limit_down_no_sell_fill; buy may fill",
        "band": "order limit price must lie within [limit_down_price, limit_up_price]; slipped fill price is capped at the band edge and flagged",
        "no_band": "no band check; flagged in result",
    },
    "price": {
        "tick_alignment": "observed price and band prices must be tick aligned",
        "buy_fill": "ceil_to_tick(observed * (1 + slippage_rate))",
        "sell_fill": "floor_to_tick(observed * (1 - slippage_rate))",
        "limit_price": "buy fill > limit -> unfilled:fill_price_exceeds_limit_price; sell fill < limit -> unfilled:fill_price_below_limit_price",
        "slippage_cost": "informational = |fill - observed| * quantity; already inside gross_amount, never added again",
    },
    "quantity": {
        "buy": "order quantity >= min_buy_quantity and multiple of buy_increment; else rejected:quantity_not_in_lot_policy",
        "sell": "order quantity <= settled sellable quantity; odd lots per declared odd_lot_sell_rule",
        "capacity": "allowance = floor(capacity * max_participation_rate) - consumed_quantity; CNY capacity converted at the fill price; rounded down to the side increment",
        "partial": "filled = min(order quantity, allowance); allowance below one increment (or below min_buy_quantity for buys) -> unfilled",
    },
    "fees": {
        "commission": "max(round_half_up_0.01(gross * side_commission_rate), min_commission)",
        "transfer_fee": "round_half_up_0.01(gross * transfer_fee_rate) both sides",
        "stamp_duty": "round_half_up_0.01(gross * sell_stamp_duty_rate) sell side only",
        "buy_affordability": "gross + commission + transfer_fee <= available_cash, checked on the capacity-limited quantity before any fill is recorded",
        "sell_proceeds": "gross - commission - transfer_fee - stamp_duty; cash after fees must stay >= 0",
        "no_default_rates": True,
    },
    "settlement": {
        "sellable_after_sessions": "declared; lot acquired in session s is sellable from sessions[index(s) + n] counting halted sessions",
        "same_session_inventory": "not sellable under n >= 1",
    },
    "statuses": list(STATUSES),
    "reject_codes": list(REJECT_CODES),
    "unfilled_codes": list(UNFILLED_CODES),
    "identities": {
        "policy_hash": "sha256(canonical policy)",
        "input_hash": "sha256(canonical consumed inputs; calendar contributes only the prefix through the expiry session)",
        "result_hash": "sha256(canonical result without result_hash)",
    },
    "flags": {"review_only": True, "live_trading_enabled": False, "synthetic": "true if any input is synthetic"},
    "portfolio_interface": {
        "owner": "M4-02 (not implemented here)",
        "needs_from_kernel": ["status", "filled_quantity", "fill_price", "gross_amount", "fees", "cash_delta", "quantity_delta",
                              "sellable_from_session", "executed_at", "attempt session", "order_live_after_attempt", "capacity_remaining_after"],
        "must_supply_to_kernel": ["sized order quantity (lot-conformant)", "AccountState as of an instant <= executed_at",
                                  "capacity consumed_quantity for cumulative use of one capacity evidence",
                                  "valuation for sizing from prices observed at or before the decision instant"],
        "remaining_work": ["allocation / max exposure", "stop-loss / exit priority", "cooldown in exchange sessions", "FIFO lots and realized PnL",
                           "benchmark and delisting handling", "multi-order sequencing within a session"],
    },
}
POLICY: dict[str, Any] = json.loads(canonical_json(_POLICY_SOURCE))
POLICY_HASH = sha256_text(canonical_json(_POLICY_SOURCE))


# --------------------------------------------------------------------------------------
# result
# --------------------------------------------------------------------------------------

@dataclass(frozen=True)
class ExecutionResult:
    status: str
    reasons: tuple[dict[str, Any], ...]
    record: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return dict(self.record)

    @property
    def result_hash(self) -> str:
        return self.record["result_hash"]

    @property
    def filled_quantity(self) -> int:
        return self.record["fill"]["filled_quantity"]

    @property
    def cash_delta(self) -> Decimal:
        return Decimal(self.record["ledger_entry"]["cash_delta"]) if self.record["ledger_entry"] else Decimal(0)


class _Reject(Exception):
    def __init__(self, code: str, detail: str, **extra: Any) -> None:
        super().__init__(code)
        self.code, self.detail, self.extra = code, detail, extra


class _Unfilled(Exception):
    def __init__(self, code: str, detail: str, **extra: Any) -> None:
        super().__init__(code)
        self.code, self.detail, self.extra = code, detail, extra


def _reason(code: str, detail: str, **extra: Any) -> dict[str, Any]:
    return {"code": code, "detail": detail, **extra}


def _empty_fill() -> dict[str, Any]:
    return {"filled_quantity": 0, "fill_price": None, "reference_price": None, "gross_amount": "0.00",
            "fees": {"commission": "0.00", "transfer_fee": "0.00", "stamp_duty": "0.00", "total": "0.00"},
            "slippage_cost_informational": "0.00", "fill_recorded": False}


def _finish(status: str, reasons: list[dict[str, Any]], body: dict[str, Any]) -> ExecutionResult:
    record = {"schema": f"{CONTRACT_NAMESPACE}.result.v1", "contract_version": CONTRACT_VERSION, "policy_hash": POLICY_HASH,
              "status": status, "reasons": reasons, **body, "review_only": True, "live_trading_enabled": False}
    record["result_hash"] = sha256_text(canonical_json(record))
    return ExecutionResult(status=status, reasons=tuple(reasons), record=json.loads(canonical_json(record)))


def execute(request: ExecutionRequest) -> ExecutionResult:
    """Evaluate one execution attempt.  Never raises for domain problems: malformed input
    and every prerequisite failure come back as ``rejected`` with structured reasons and
    zero cash/position effect."""

    try:
        request.validated()
    except ExecutionInputError as exc:
        return _finish(STATUS_REJECTED, [_reason(exc.code, exc.detail)],
                       {"identities": {"input_hash": None, "policy_hash": POLICY_HASH}, "synthetic": None, "temporal": None,
                        "evidence": None, "fill": _empty_fill(), "ledger_entry": None, "order_live_after_attempt": False})
    try:
        return _evaluate(request)
    except ExecutionInputError as exc:
        return _finish(STATUS_REJECTED, [_reason(exc.code, exc.detail)],
                       {"identities": {"input_hash": None, "policy_hash": POLICY_HASH}, "synthetic": request.is_synthetic(),
                        "temporal": None, "evidence": None, "fill": _empty_fill(), "ledger_entry": None,
                        "order_live_after_attempt": False})


def _evaluate(req: ExecutionRequest) -> ExecutionResult:
    d, o, inst, cal, trad, px, acct, fees, asm, att, cap = (req.decision, req.order, req.instrument, req.calendar,
                                                            req.tradability, req.price, req.account, req.fee_schedule,
                                                            req.assumptions, req.attempt, req.capacity)
    reasons: list[dict[str, Any]] = []
    flags: list[str] = []
    assumed_states: dict[str, str] = {}
    body: dict[str, Any] = {}
    identity = {"decision_id": d.decision_id, "order_id": o.order_id, "attempt_id": att.attempt_id, "symbol": o.symbol,
                "side": o.side, "role": inst.role, "board": inst.board}
    body["identity"] = identity
    body["synthetic"] = req.is_synthetic()
    try:
        # ---- identity consistency ------------------------------------------------------
        symbols = {d.symbol, o.symbol, inst.symbol, trad.symbol, px.symbol} | ({cap.symbol} if cap else set())
        if len(symbols) != 1:
            raise _Reject("symbol_mismatch", f"symbols differ across inputs: {sorted(symbols)}")
        if d.side != o.side:
            raise _Reject("side_mismatch", f"decision side {d.side} != order side {o.side}")
        if o.decision_id != d.decision_id:
            raise _Reject("decision_id_mismatch", f"order references {o.decision_id}, decision is {d.decision_id}")
        if inst.role != ROLE_STOCK:
            raise _Reject("non_tradable_role", f"role {inst.role} is not tradable (benchmarks/indices are never executed)")
        if inst.calendar_ref != cal.source_ref:
            raise _Reject("calendar_mismatch", f"instrument calendar_ref {inst.calendar_ref!r} != calendar source_ref {cal.source_ref!r}")

        # ---- temporal chain --------------------------------------------------------------
        index = cal.index()
        if d.decision_session not in index:
            raise _Reject("decision_session_not_in_calendar", f"{d.decision_session} is not a calendar session")
        decided_at = _instant(d.decided_at, "invalid_input", "decided_at")
        for item in d.inputs:
            if _instant(item.available_at, "invalid_input", "input available_at") > decided_at:
                raise _Reject("input_not_available_at_decision", f"input {item.name} available at {item.available_at} after decided_at {d.decided_at}",
                              input=item.name)
        dec_idx = index[d.decision_session]
        if decided_at < cal.close_at(d.decision_session):
            raise _Reject("decision_before_session_close", f"decided_at {d.decided_at} precedes close of {d.decision_session}")
        if dec_idx + 1 >= len(cal.sessions):
            raise _Reject("next_session_beyond_calendar", f"no session after {d.decision_session} in the injected calendar")
        next_session = cal.sessions[dec_idx + 1]
        next_open = cal.open_at(next_session)
        if decided_at >= next_open:
            raise _Reject("decision_after_next_session_open", f"decided_at {d.decided_at} is not before open of {next_session}; not a prior-close decision")
        submitted_at = _instant(o.submitted_at, "invalid_input", "submitted_at")
        eligible_from = _instant(o.eligible_from, "invalid_input", "eligible_from")
        if submitted_at < decided_at:
            raise _Reject("submitted_before_decision", f"submitted_at {o.submitted_at} precedes decided_at {d.decided_at}")
        if submitted_at > eligible_from:
            raise _Reject("submitted_after_eligible", f"submitted_at {o.submitted_at} is after eligible_from {o.eligible_from}")
        if eligible_from < next_open:
            raise _Reject("eligible_before_next_session_open", f"eligible_from {o.eligible_from} precedes open of next session {next_session} ({next_open.isoformat()})")
        eligible_session = cal.local_date(eligible_from)
        if eligible_session not in index or not (cal.open_at(eligible_session) <= eligible_from <= cal.close_at(eligible_session)):
            raise _Reject("eligible_from_not_in_session", f"eligible_from {o.eligible_from} is not inside a calendar session")
        exp_idx = index[eligible_session] + o.expiry_sessions - 1
        if exp_idx >= len(cal.sessions):
            raise _Reject("expiry_beyond_calendar", f"expiry needs session index {exp_idx}, calendar has {len(cal.sessions)}")
        expiry_session = cal.sessions[exp_idx]
        expires_at = cal.close_at(expiry_session)
        window_sessions = cal.sessions[index[eligible_session]: exp_idx + 1]
        halted_in_window = [h for h in cal.halted_sessions if h in window_sessions]
        executed_at = _instant(att.executed_at, "invalid_input", "executed_at")
        exec_session = cal.local_date(executed_at)
        if exec_session not in index or not (cal.open_at(exec_session) <= executed_at <= cal.close_at(exec_session)):
            raise _Reject("execution_outside_session", f"executed_at {att.executed_at} is not inside a calendar session")
        if att.session != exec_session:
            raise _Reject("attempt_session_mismatch", f"attempt.session {att.session} != session of executed_at {exec_session}")
        if executed_at < eligible_from:
            raise _Reject("execution_before_eligible", f"executed_at {att.executed_at} precedes eligible_from {o.eligible_from}")
        if executed_at > expires_at:
            raise _Reject("order_expired", f"executed_at {att.executed_at} is after expiry {expires_at.isoformat()} (expiry session {expiry_session}, {o.expiry_sessions} session(s) incl. halted {halted_in_window})")
        if att.phase != o.execution_phase:
            raise _Reject("execution_phase_mismatch", f"attempt phase {att.phase} != order phase {o.execution_phase}")
        s_open, s_close = cal.open_at(exec_session), cal.close_at(exec_session)
        if att.phase == PHASE_OPEN_AUCTION and executed_at != s_open:
            raise _Reject("execution_phase_mismatch", f"open_auction attempt must be at {s_open.isoformat()}, got {att.executed_at}")
        if att.phase == PHASE_CONTINUOUS and not (s_open < executed_at < s_close):
            raise _Reject("execution_phase_mismatch", f"continuous attempt must be strictly inside ({s_open.isoformat()}, {s_close.isoformat()})")
        if att.phase == PHASE_CLOSE_AUCTION and executed_at != s_close:
            raise _Reject("execution_phase_mismatch", f"close_auction attempt must be at {s_close.isoformat()}, got {att.executed_at}")
        body["temporal"] = {
            "decision_session": d.decision_session, "decided_at": decided_at.isoformat(),
            "inputs_available_at_max": max(_instant(i.available_at, "invalid_input", "x") for i in d.inputs).isoformat(),
            "submitted_at": submitted_at.isoformat(), "next_session": next_session, "next_session_open": next_open.isoformat(),
            "eligible_from": eligible_from.isoformat(), "eligible_session": eligible_session, "expiry_sessions": o.expiry_sessions,
            "expiry_session": expiry_session, "expires_at": expires_at.isoformat(), "window_sessions": list(window_sessions),
            "halted_sessions_in_window": halted_in_window, "executed_at": executed_at.isoformat(), "execution_session": exec_session,
            "execution_phase": att.phase, "sessions_elapsed_in_window": index[exec_session] - index[eligible_session] + 1,
            "expires_after_this_session": exec_session == expiry_session,
        }

        # ---- evidence timing -----------------------------------------------------------
        if trad.session != exec_session:
            raise _Reject("evidence_session_mismatch", f"tradability evidence is for {trad.session}, execution session is {exec_session}")
        for label, obs, avail in (("tradability", trad.observed_at, trad.available_at), ("price", px.observed_at, px.available_at)):
            if _instant(obs, "invalid_input", "x") > executed_at:
                raise _Reject("evidence_observed_after_execution", f"{label} observed at {obs}, after executed_at {att.executed_at}", evidence=label)
        if _instant(trad.available_at, "invalid_input", "x") > executed_at:
            raise _Reject("evidence_available_after_execution", f"tradability available at {trad.available_at}, after executed_at {att.executed_at}", evidence="tradability")
        if cal.local_date(_instant(px.observed_at, "invalid_input", "x")) != exec_session:
            raise _Reject("evidence_session_mismatch", f"price observed on {cal.local_date(_instant(px.observed_at, 'invalid_input', 'x'))}, not the execution session {exec_session}")
        if px.kind == EVIDENCE_CONTEMPORANEOUS and _instant(px.available_at, "invalid_input", "x") > executed_at:
            raise _Reject("evidence_available_after_execution", f"contemporaneous price available at {px.available_at}, after executed_at {att.executed_at}", evidence="price")
        if cap is not None:
            if _instant(cap.observed_at, "invalid_input", "x") > executed_at:
                raise _Reject("evidence_observed_after_execution", f"capacity observed at {cap.observed_at}, after executed_at {att.executed_at}", evidence="capacity")
            if cal.local_date(_instant(cap.observed_at, "invalid_input", "x")) != exec_session:
                raise _Reject("evidence_session_mismatch", "capacity observed on another session")
            if cap.kind == EVIDENCE_CONTEMPORANEOUS and _instant(cap.available_at, "invalid_input", "x") > executed_at:
                raise _Reject("evidence_available_after_execution", f"contemporaneous capacity available at {cap.available_at}, after executed_at {att.executed_at}", evidence="capacity")
        if _instant(acct.as_of, "invalid_input", "x") > executed_at:
            raise _Reject("account_state_after_execution", f"account state as_of {acct.as_of} is after executed_at {att.executed_at}")
        assumptions_used: list[str] = []
        if px.kind == EVIDENCE_ASSUMPTION:
            assumptions_used.append(f"price:{px.assumption_ref}")
        if cap is not None and cap.kind == EVIDENCE_ASSUMPTION:
            assumptions_used.append(f"capacity:{cap.assumption_ref}")

        # ---- tradability, unknown states, band ------------------------------------------
        if trad.status == "unknown":
            raise _Reject("tradability_unknown", "tradability status is unknown; not treated as tradable")
        states = {"limit_state": trad.limit_state, "band_state": trad.band_state, "st_status": trad.st_status, "listing_state": trad.listing_state}
        declared = asm.assumed()
        for fld, val in states.items():
            if val == "unknown":
                if fld not in declared:
                    raise _Reject("unknown_state", f"{fld} is unknown and no explicit assumption was declared", field=fld)
                states[fld] = declared[fld]
                assumed_states[fld] = declared[fld]
                assumptions_used.append(f"{fld}:{declared[fld]}:{asm.assumption_id}")
        tick = _money(asm.tick_size, "invalid_input", "tick_size")
        ref_price = _money(px.price, "invalid_input", "observed price")
        if not is_tick_aligned(ref_price, tick):
            raise _Reject("price_not_tick_aligned", f"observed price {ref_price} is not a multiple of tick {tick}")
        limit_price = o.limit()
        if not is_tick_aligned(limit_price, tick):
            raise _Reject("price_not_tick_aligned", f"order limit price {limit_price} is not a multiple of tick {tick}")
        band_lo = band_hi = None
        if states["band_state"] == "band":
            if trad.limit_up_price is None or trad.limit_down_price is None:
                raise _Reject("band_prices_missing", "band_state=band requires limit_up_price and limit_down_price")
            band_hi = _money(trad.limit_up_price, "invalid_input", "limit_up_price")
            band_lo = _money(trad.limit_down_price, "invalid_input", "limit_down_price")
            if band_lo >= band_hi or not is_tick_aligned(band_lo, tick) or not is_tick_aligned(band_hi, tick):
                raise _Reject("band_prices_invalid", f"band [{band_lo}, {band_hi}] must be tick aligned with down < up")
            if not (band_lo <= limit_price <= band_hi):
                raise _Reject("limit_price_outside_band", f"order limit {limit_price} outside band [{band_lo}, {band_hi}]")
            if not (band_lo <= ref_price <= band_hi):
                raise _Reject("band_prices_invalid", f"observed price {ref_price} outside its own band [{band_lo}, {band_hi}]")
        else:
            flags.append("no_price_band")
        if states["st_status"] == "st":
            flags.append("st_security")
        if states["listing_state"] == "new_listing":
            flags.append("new_listing")
        body["evidence"] = {
            "tradability": {"status": trad.status, "limit_state": states["limit_state"], "band_state": states["band_state"],
                            "st_status": states["st_status"], "listing_state": states["listing_state"],
                            "limit_up_price": str(band_hi) if band_hi is not None else None, "limit_down_price": str(band_lo) if band_lo is not None else None,
                            "observed_at": trad.observed_at, "available_at": trad.available_at, "source_ref": trad.source_ref},
            "price": {"price": str(ref_price), "field": px.field, "kind": px.kind, "observed_at": px.observed_at, "available_at": px.available_at,
                      "source_ref": px.source_ref, "assumption_ref": px.assumption_ref},
            "capacity": None if cap is None else {"capacity_id": cap.capacity_id, "quantity": str(cap.quantity), "unit": cap.unit, "basis": cap.basis,
                                                   "kind": cap.kind, "observed_at": cap.observed_at, "available_at": cap.available_at,
                                                   "source_ref": cap.source_ref, "assumption_ref": cap.assumption_ref,
                                                   "consumed_quantity_before": cap.consumed_quantity},
            "assumed_states": dict(sorted(assumed_states.items())),
            "assumptions_used": sorted(assumptions_used),
            "evidence_grade": EVIDENCE_CONTEMPORANEOUS if not assumptions_used else "assumed",
        }

        # ---- lot policy and inventory --------------------------------------------------
        lot = asm.lot_policy
        if o.quantity > lot.max_order_quantity:
            raise _Reject("quantity_not_in_lot_policy", f"quantity {o.quantity} exceeds max_order_quantity {lot.max_order_quantity}")
        held_total = sum(l.quantity for l in acct.inventory)
        settle_n = asm.settlement_policy.sellable_after_sessions
        settled = 0
        for l in acct.inventory:
            if l.acquired_session not in index:
                raise ExecutionInputError("invalid_input", f"inventory lot acquired_session {l.acquired_session} not in calendar")
            if index[l.acquired_session] + settle_n <= index[exec_session]:
                settled += l.quantity
        unsettled = held_total - settled
        if o.side == SIDE_BUY:
            if o.quantity < lot.min_buy_quantity or o.quantity % lot.buy_increment:
                raise _Reject("quantity_not_in_lot_policy", f"buy quantity {o.quantity} must be >= {lot.min_buy_quantity} and a multiple of {lot.buy_increment}")
        else:
            if o.quantity > settled:
                raise _Reject("insufficient_settled_inventory", f"sell {o.quantity} exceeds settled sellable {settled} (held {held_total}, unsettled {unsettled}, T+{settle_n} on exchange sessions)",
                              settled_sellable=settled, held_total=held_total, unsettled=unsettled)
            odd = o.quantity % lot.sell_increment
            if odd:
                if lot.odd_lot_sell_rule == "forbidden":
                    raise _Reject("odd_lot_rule_violation", f"sell quantity {o.quantity} is not a multiple of {lot.sell_increment} and odd lots are forbidden")
                if lot.odd_lot_sell_rule == "whole_odd_remainder_only" and odd != settled % lot.sell_increment:
                    raise _Reject("odd_lot_rule_violation", f"odd part {odd} must equal the whole settled odd remainder {settled % lot.sell_increment}")
        body["inventory"] = {"held_total": held_total, "settled_sellable": settled, "unsettled": unsettled,
                             "settlement_policy": asm.settlement_policy.policy_id, "sellable_after_sessions": settle_n,
                             "lot_policy": lot.policy_id, "available_cash_before": str(quantize_money(acct.cash()))}

        # ---- fee schedule applicability ----------------------------------------------
        ok, why = fees.applies(exec_session, inst.board)
        if not ok:
            raise _Reject("fee_schedule_not_applicable", f"{fees.schedule_id}@{fees.version}: {why}")
        body["fee_schedule"] = {"schedule_id": fees.schedule_id, "version": fees.version, "provenance": fees.provenance,
                                "source_ref": fees.source_ref, "effective_from": fees.effective_from, "effective_to": fees.effective_to,
                                "rounding": fees.rounding}
        body["assumptions"] = {"assumption_id": asm.assumption_id, "provenance": asm.provenance, "source_ref": asm.source_ref,
                               "slippage_rate": str(_rate(asm.slippage_rate, "invalid_input", "x", maximum=MAX_SLIPPAGE)),
                               "max_participation_rate": str(_rate(asm.max_participation_rate, "invalid_input", "x", maximum=Decimal(1))),
                               "tick_size": str(tick)}

        # ---- side-specific limit state / suspension (valid order, may not fill) ----------
        if trad.status == "suspended":
            raise _Unfilled("suspended", f"{o.symbol} is suspended on {exec_session}; order remains live until {expires_at.isoformat()}")
        if states["limit_state"] == "limit_up" and o.side == SIDE_BUY:
            raise _Unfilled("limit_up_no_buy_fill", "one-sided limit-up market: buy orders do not fill")
        if states["limit_state"] == "limit_down" and o.side == SIDE_SELL:
            raise _Unfilled("limit_down_no_sell_fill", "one-sided limit-down market: sell orders do not fill")

        # ---- fill price ------------------------------------------------------------------
        slip = _rate(asm.slippage_rate, "invalid_input", "x", maximum=MAX_SLIPPAGE)
        if o.side == SIDE_BUY:
            fill_price = round_to_tick(ref_price * (Decimal(1) + slip), tick, "up")
            if band_hi is not None and fill_price > band_hi:
                fill_price = band_hi
                flags.append("slippage_capped_at_band")
            if fill_price > limit_price:
                raise _Unfilled("fill_price_exceeds_limit_price", f"buy fill price {fill_price} > limit {limit_price}", fill_price=str(fill_price))
        else:
            fill_price = round_to_tick(ref_price * (Decimal(1) - slip), tick, "down")
            if band_lo is not None and fill_price < band_lo:
                fill_price = band_lo
                flags.append("slippage_capped_at_band")
            if fill_price < limit_price:
                raise _Unfilled("fill_price_below_limit_price", f"sell fill price {fill_price} < limit {limit_price}", fill_price=str(fill_price))

        # ---- capacity ------------------------------------------------------------------
        if cap is None:
            raise _Unfilled("capacity_unproven", "no execution-time capacity evidence; a fill cannot be proven and is not invented")
        rate = _rate(asm.max_participation_rate, "invalid_input", "x", maximum=Decimal(1))
        if cap.unit == "share":
            allowance = int((Decimal(cap.quantity) * rate).to_integral_value(rounding=ROUND_FLOOR))
        else:
            allowance = int((_money(cap.quantity, "invalid_input", "x", allow_zero=True) * rate / fill_price).to_integral_value(rounding=ROUND_FLOOR))
        remaining_allowance = allowance - cap.consumed_quantity
        inc = lot.buy_increment if o.side == SIDE_BUY else lot.sell_increment
        fillable = max(0, remaining_allowance) // inc * inc
        capacity_info = {"capacity_id": cap.capacity_id, "allowance_quantity": allowance, "consumed_before": cap.consumed_quantity,
                         "remaining_allowance_before": remaining_allowance, "increment": inc}
        if remaining_allowance <= 0:
            raise _Unfilled("capacity_exhausted", f"participation allowance {allowance} already consumed ({cap.consumed_quantity})", **capacity_info)
        if fillable <= 0 or (o.side == SIDE_BUY and fillable < lot.min_buy_quantity):
            raise _Unfilled("capacity_below_minimum_lot", f"remaining allowance {remaining_allowance} rounds to {fillable} < minimum lot", **capacity_info)
        filled = min(o.quantity, fillable)
        if o.side == SIDE_SELL and filled < o.quantity and lot.odd_lot_sell_rule == "whole_odd_remainder_only" and filled % lot.sell_increment:
            filled = filled // lot.sell_increment * lot.sell_increment
            if filled <= 0:
                raise _Unfilled("capacity_below_minimum_lot", "partial sell would break the odd-lot rule", **capacity_info)
        status = STATUS_FILLED if filled == o.quantity else STATUS_PARTIAL

        # ---- fees and cash (checked before any fill is recorded) --------------------------
        gross = quantize_money(fill_price * Decimal(filled))
        comm_rate = _rate(fees.buy_commission_rate if o.side == SIDE_BUY else fees.sell_commission_rate, "invalid_input", "x")
        commission = max(quantize_money(gross * comm_rate), quantize_money(_money(fees.min_commission, "invalid_input", "x", allow_zero=True)))
        transfer = quantize_money(gross * _rate(fees.transfer_fee_rate, "invalid_input", "x"))
        stamp = quantize_money(gross * _rate(fees.sell_stamp_duty_rate, "invalid_input", "x")) if o.side == SIDE_SELL else Decimal("0.00")
        total_fees = commission + transfer + stamp
        cash_before = quantize_money(acct.cash())
        if o.side == SIDE_BUY:
            total_cost = gross + total_fees
            if total_cost > cash_before:
                raise _Reject("insufficient_cash", f"buy needs {total_cost} (gross {gross} + fees {total_fees}) but available cash is {cash_before}",
                              required=str(total_cost), available=str(cash_before), shortfall=str(total_cost - cash_before), attempted_quantity=filled)
            cash_delta, qty_delta = -total_cost, filled
        else:
            proceeds = gross - total_fees
            if cash_before + proceeds < 0:
                raise _Reject("negative_cash_after_fees", f"sell proceeds {proceeds} would leave cash negative")
            cash_delta, qty_delta = proceeds, -filled
        slippage_cost = quantize_money(abs(fill_price - ref_price) * Decimal(filled))
        sellable_idx = index[exec_session] + settle_n
        sellable_from = cal.sessions[sellable_idx] if sellable_idx < len(cal.sessions) else None
        if o.side == SIDE_BUY and sellable_from is None:
            flags.append("sellable_session_beyond_calendar")
        body["fill"] = {"filled_quantity": filled, "requested_quantity": o.quantity, "remaining_quantity": o.quantity - filled,
                        "fill_price": str(fill_price), "reference_price": str(ref_price), "limit_price": str(limit_price), "gross_amount": str(gross),
                        "fees": {"commission": str(commission), "transfer_fee": str(transfer), "stamp_duty": str(stamp), "total": str(total_fees)},
                        "slippage_cost_informational": str(slippage_cost), "fill_recorded": True,
                        "capacity": {**capacity_info, "consumed_after": cap.consumed_quantity + filled, "remaining_allowance_after": remaining_allowance - filled}}
        body["ledger_entry"] = {"side": o.side, "symbol": o.symbol, "session": exec_session, "executed_at": executed_at.isoformat(),
                                "quantity_delta": qty_delta, "cash_delta": str(cash_delta), "cash_after": str(cash_before + cash_delta),
                                "gross_amount": str(gross), "fees": dict(body["fill"]["fees"]), "fill_price": str(fill_price),
                                "reference_price": str(ref_price), "slippage_cost_included_in_gross": True,
                                "sellable_from_session": sellable_from if o.side == SIDE_BUY else None,
                                "settled_sellable_after": settled - filled if o.side == SIDE_SELL else settled,
                                "fee_schedule": f"{fees.schedule_id}@{fees.version}", "currency": fees.currency}
        body["order_live_after_attempt"] = status == STATUS_PARTIAL and exec_session != expiry_session
        body["flags"] = sorted(set(flags))
        body["identities"] = _identities(req, expiry_session)
        return _finish(status, reasons, body)
    except _Reject as exc:
        reasons.append(_reason(exc.code, exc.detail, **exc.extra))
        body.setdefault("temporal", None)
        body.setdefault("evidence", None)
        body["fill"] = _empty_fill()
        body["ledger_entry"] = None
        body["order_live_after_attempt"] = False
        body["flags"] = sorted(set(flags))
        body["identities"] = _identities(req, body["temporal"]["expiry_session"] if body.get("temporal") else None)
        return _finish(STATUS_REJECTED, reasons, body)
    except _Unfilled as exc:
        reasons.append(_reason(exc.code, exc.detail, **exc.extra))
        body["fill"] = _empty_fill()
        body["ledger_entry"] = None
        body["order_live_after_attempt"] = not body["temporal"]["expires_after_this_session"]
        body["flags"] = sorted(set(flags))
        body["identities"] = _identities(req, body["temporal"]["expiry_session"])
        return _finish(STATUS_UNFILLED, reasons, body)


def _identities(req: ExecutionRequest, expiry_session: str | None) -> dict[str, Any]:
    cal_rec = req.calendar.prefix_record(expiry_session) if expiry_session else {"prefix_fingerprint": None, "full_fingerprint": req.calendar.fingerprint()}
    consumed = {"decision": _record(req.decision), "order": _record(req.order), "instrument": _record(req.instrument), "calendar": cal_rec,
                "tradability": _record(req.tradability), "price": _record(req.price), "capacity": _record(req.capacity),
                "account": _record(req.account), "fee_schedule": _record(req.fee_schedule), "assumptions": _record(req.assumptions),
                "attempt": _record(req.attempt)}
    input_hash = sha256_text(canonical_json(consumed))
    return {"input_hash": input_hash, "policy_hash": POLICY_HASH, "contract_version": CONTRACT_VERSION,
            "calendar_prefix_fingerprint": cal_rec.get("prefix_fingerprint"), "calendar_prefix_last_session": expiry_session,
            "fee_schedule": f"{req.fee_schedule.schedule_id}@{req.fee_schedule.version}", "assumption_id": req.assumptions.assumption_id}


__all__ = [
    "CONTRACT_VERSION", "POLICY", "POLICY_HASH", "ExecutionInputError", "SessionCalendar", "InputAvailability", "Decision", "Order",
    "Instrument", "TradabilityEvidence", "PriceObservation", "LiquidityCapacity", "InventoryLot", "AccountState", "FeeSchedule",
    "LotPolicy", "SettlementPolicy", "ExecutionAssumptions", "ExecutionAttempt", "ExecutionRequest", "ExecutionResult", "execute",
    "canonical_json", "sha256_text", "quantize_money", "round_to_tick", "is_tick_aligned",
]
