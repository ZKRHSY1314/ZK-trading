"""Causal evidence mapping for the M4-03B proposal (M4-03A delivery 02) - pure functions, no I/O, no engine import.

The mapping turns one frozen daily bar plus its capture provenance into the inputs of the accepted kernel / ledger /
risk layer, keeping RAW capture instants and MODEL (assumed) instants in separate fields:

* every object carries the raw capture instant verbatim inside ``source_ref`` (``captured=<row_evidence.observed_at>``);
  the raw instant is never overwritten;
* under ``variant="raw"`` the raw capture instant IS the observed/available instant (strict-raw path: nothing is
  assumed, and the accepted engines refuse 2026-captured evidence for 2023-2025 instants);
* under ``variant="assumed"`` the model instants are declared per field: close fields become observable at the
  session close (15:00+08:00) and available at close + 3600 s (the M3 ``close+3600s`` convention); the open field is
  observable/available only at the declared 09:30+08:00 open-auction instant of its own session; each declared
  instant names its assumption id.

Causality by construction: ``attempt_evidence`` accepts only the OPEN print of the attempt session and the previous
session's close/halt facts - high/low/close/volume of the attempt session and anything later cannot reach the attempt
(``future_suffix_invariance`` in validate_qualification.py proves it against the frozen engines).

Capacity: two fixed, mutually exclusive variants, both independent of full-day volume and both mathematically
consistent with the kernel's ``allowance = floor(capacity x max_participation_rate)`` (participation is 1.0 in both):
``full_fill`` (capacity = order quantity -> allowance = order quantity) and ``fixed_5000`` (capacity = 5 000 shares per
open attempt -> partial fills in whole lots).  ``none`` (STRICT capacity-removal sensitivity) injects no capacity.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

TZ = "+08:00"
OPEN_TIME = "09:30:00"
CLOSE_TIME = "15:00:00"
DECISION_TIME = "16:00:00"                       # close + 3600 s
CLOSE_AVAILABILITY_OFFSET_SECONDS = 3600
CALENDAR_ASSUMED_AVAILABLE_AT = "2022-08-24T00:00:00+08:00"   # first warmup session of the frozen window
NEW_LISTING_SESSIONS = 5
VARIANTS = ("raw", "assumed")
CAPACITY_VARIANTS = ("none", "full_fill", "fixed_5000")
FIXED_CAPACITY_SHARES = 5000
ASSUMPTIONS = {
    "close_availability": "ASSUMPTION:close_fields_observed_at_1500_available_at_close_plus_3600s",
    "open_print": "ASSUMPTION:daily_bar_open_equals_0930_auction_print",
    "calendar": "ASSUMPTION:exchange_calendar_published_in_advance",
    "tradable": "ASSUMPTION:open_print_present_and_no_full_day_halt_key_implies_tradable_at_open",
    "band": "ASSUMPTION:band_from_previous_close_and_code_prefix_ratio_rounded_half_up_to_tick",
    "limit_state": "ASSUMPTION:limit_state_from_open_print_versus_band_only",
    "st": "ASSUMPTION:st_status_not_st",
    "listing": "ASSUMPTION:listing_state_seasoned_after_5_sessions",
    "capacity_full_fill": "ASSUMPTION:full_fill_capacity_equals_order_quantity_participation_1.0",
    "capacity_fixed_5000": "ASSUMPTION:fixed_exogenous_capacity_5000_shares_per_open_attempt_participation_1.0",
    "halt_placeholder": "ASSUMPTION:full_day_halt_no_print_previous_close_placeholder_cannot_fill_status_suspended",
    "ex_date_flag": "POST_HOC_FLAG:position_window_contains_known_ex_date_original_availability_not_established",
}
BOARD_RATIOS = {"main": Decimal("0.10"), "star": Decimal("0.20"), "chinext": Decimal("0.20"), "bse": Decimal("0.30")}


def board_by_code_prefix(symbol: str) -> str:
    """Declared code-prefix board hypothesis (not evidence): SH688 -> star; SZ300/SZ301 -> chinext; BJ -> bse; else main."""
    if symbol.startswith("SH688"):
        return "star"
    if symbol.startswith(("SZ300", "SZ301")):
        return "chinext"
    if symbol.startswith("BJ"):
        return "bse"
    return "main"


def close_times(session: str) -> tuple[str, str]:
    """MODEL instants for close fields: observed at the close, available at close + 3600 s."""
    return f"{session}T{CLOSE_TIME}{TZ}", f"{session}T{DECISION_TIME}{TZ}"


def open_times(session: str) -> tuple[str, str]:
    """MODEL instants for the open print: observed and available at the declared 09:30 auction instant."""
    return f"{session}T{OPEN_TIME}{TZ}", f"{session}T{OPEN_TIME}{TZ}"


def provenance(captured_at: str, assumption_ids: tuple[str, ...], raw_ref: str) -> str:
    """source_ref text: the raw capture instant verbatim plus the assumption ids that produced the model instants."""
    ids = ";".join(assumption_ids) if assumption_ids else "none"
    return f"{raw_ref}; captured={captured_at}; assumptions={ids}"


def assumed_band(prev_close: Decimal, board: str, tick: Decimal = Decimal("0.01")) -> tuple[Decimal, Decimal]:
    """Hypothetical daily band from the previous close and the code-prefix ratio, rounded half-up to the tick."""
    r = BOARD_RATIOS[board]
    hi = (prev_close * (Decimal(1) + r)).quantize(tick, rounding=ROUND_HALF_UP)
    lo = (prev_close * (Decimal(1) - r)).quantize(tick, rounding=ROUND_HALF_UP)
    return lo, hi


def limit_state_from_open(open_price: Decimal, lo: Decimal, hi: Decimal) -> str:
    """Only the open print and the previous-close band decide the state at the open attempt."""
    if open_price >= hi:
        return "limit_up"
    if open_price <= lo:
        return "limit_down"
    return "none"


def mark(r: Any, symbol: str, session: str, close: Any, captured_at: str, variant: str, synthetic: bool):
    """Risk-layer valuation mark from a session close (raw: capture instants; assumed: 15:00 / 16:00 of its own session)."""
    if variant not in VARIANTS:
        raise ValueError(variant)
    if variant == "raw":
        return r.Mark(symbol, close, captured_at, captured_at, provenance(captured_at, (), "RAW:daily_bar_cache.close"), synthetic)
    observed, available = close_times(session)
    return r.Mark(symbol, close, observed, available, provenance(captured_at, (ASSUMPTIONS["close_availability"],), "MODEL:daily_bar_cache.close"), synthetic)


def benchmark_level(r: Any, symbol: str, session: str, close: Any, captured_at: str, variant: str, synthetic: bool):
    if variant == "raw":
        return r.BenchmarkObservation(symbol, close, captured_at, captured_at, provenance(captured_at, (), "RAW:daily_bar_cache.close[index]"), synthetic)
    observed, available = close_times(session)
    return r.BenchmarkObservation(symbol, close, observed, available, provenance(captured_at, (ASSUMPTIONS["close_availability"],), "MODEL:daily_bar_cache.close[index]"), synthetic)


def signal(r: Any, signal_id: str, symbol: str, session: str, captured_at: str, variant: str, synthetic: bool):
    """A rule signal evaluated on closes up to ``session``: same instants as the close it depends on."""
    if variant == "raw":
        return r.Signal(signal_id, symbol, "buy", captured_at, captured_at, provenance(captured_at, (), "RAW:rule_on_close"), synthetic)
    observed, available = close_times(session)
    return r.Signal(signal_id, symbol, "buy", observed, available, provenance(captured_at, (ASSUMPTIONS["close_availability"],), "MODEL:rule_on_close"), synthetic)


def calendar(k: Any, sessions: tuple[str, ...], captured_at: str, variant: str, synthetic: bool, calendar_ref: str):
    available = captured_at if variant == "raw" else CALENDAR_ASSUMED_AVAILABLE_AT
    ids = () if variant == "raw" else (ASSUMPTIONS["calendar"],)
    return k.SessionCalendar(sessions, TZ, "09:30", "15:00", provenance(captured_at, ids, calendar_ref), available, synthetic, ())


def decision_context(r: Any, session: str, cal: Any, fees: Any, assumptions: Any):
    return r.DecisionContext(session, f"{session}T{DECISION_TIME}{TZ}", cal, fees, assumptions)


def execution_assumptions(k: Any, assumption_id: str = "HYPOTHETICAL_FIXTURE_ASSUMPTIONS_03B", declare_unknown_states: bool = True):
    """Fixture assumptions of the proposal: slippage 0.002, participation 1.0 (capacity is already an assumption), tick 0.01,
    100-share lots, T+1; under the assumed variant the unknown tradability states are declared (st not_st, listing seasoned);
    the raw variant declares nothing, so an unknown state is refused by the kernel (unknown_state)."""
    declared = (("st_status", "not_st"), ("listing_state", "seasoned")) if declare_unknown_states else ()
    return k.ExecutionAssumptions(assumption_id, "hypothetical_fixture", "syn:proposal-assumptions", "0.002", "1", "0.01",
                                  k.LotPolicy("syn:lot_100", 100, 100, 100, "whole_odd_remainder_only", 1_000_000), k.SettlementPolicy("syn:T+1", 1), declared)


def fee_schedule(k: Any, boards: tuple[str, ...] = ("main", "star", "chinext", "bse")):
    """HYPOTHETICAL_FIXTURE_FEES_A values (kernel contract): 0.0004 / 0.0004 / 6.00 / 0.00002 / 0.0008 - fixtures, not tariffs."""
    return k.FeeSchedule("HYPOTHETICAL_FIXTURE_FEES_A", "1", "hypothetical_fixture", "syn:fee-fixture", "2022-08-24", "2025-03-31", boards,
                         "0.0004", "0.0004", "6.00", "0.00002", "0.0008")


def capacity(k: Any, symbol: str, session: str, order_quantity: int, capacity_variant: str, captured_at: str, synthetic: bool, consumed: int = 0):
    """Exogenous capacity assumption for the open attempt (never derived from daily volume)."""
    if capacity_variant not in CAPACITY_VARIANTS:
        raise ValueError(capacity_variant)
    if capacity_variant == "none":
        return None
    observed, available = open_times(session)
    if capacity_variant == "full_fill":
        qty, basis, ref = order_quantity, "hypothetical_full_fill_equals_order_quantity", ASSUMPTIONS["capacity_full_fill"]
    else:
        qty, basis, ref = FIXED_CAPACITY_SHARES, "hypothetical_fixed_exogenous_shares", ASSUMPTIONS["capacity_fixed_5000"]
    return k.LiquidityCapacity(symbol, f"CAP-{symbol}-{session}-open", qty, "share", basis, observed, available,
                               provenance(captured_at, (ref,), "MODEL:no_market_capacity_evidence"), "predeclared_assumption", synthetic, consumed, ref)


@dataclass(frozen=True)
class OpenAttemptInputs:
    """Everything the open attempt may see: the previous session's close (band), the halt ledger for the attempt session
    and the attempt session's OPEN print.  High/low/close/volume of the attempt session are not accepted here."""
    symbol: str
    session: str
    open_price: Any                 # None on a full-day halt key (no print exists)
    prev_close: Any
    full_day_halt_key: bool
    captured_at: str
    board: str
    sessions_since_listing: int | None


def attempt_evidence(k: Any, r: Any, inputs: OpenAttemptInputs, attempt_id: str, variant: str, capacity_variant: str, order_quantity: int, synthetic: bool):
    """Kernel/risk attempt evidence at ``session`` 09:30 built only from causal inputs."""
    if variant not in VARIANTS:
        raise ValueError(variant)
    tick = Decimal("0.01")
    executed_at = f"{inputs.session}T{OPEN_TIME}{TZ}"
    if variant == "raw":
        t_obs = t_avail = p_obs = p_avail = inputs.captured_at
        ids: tuple[str, ...] = ()
    else:
        t_obs, t_avail = open_times(inputs.session)
        p_obs, p_avail = open_times(inputs.session)
        ids = (ASSUMPTIONS["open_print"],)
    lo, hi = assumed_band(Decimal(str(inputs.prev_close)), inputs.board, tick)
    if inputs.full_day_halt_key:
        if inputs.open_price is not None:
            raise ValueError("a full-day halt key has no open print")
        status, limit_state = "suspended", "none"
        price_value, price_field, price_ids = str(inputs.prev_close), "previous_close_placeholder_no_print", (ASSUMPTIONS["halt_placeholder"],)
    else:
        if inputs.open_price is None:
            raise ValueError("an open attempt needs the open print of its own session")
        status, limit_state = "tradable", limit_state_from_open(Decimal(str(inputs.open_price)), lo, hi)
        price_value, price_field, price_ids = str(inputs.open_price), "open", ids
    listing_state = "new_listing" if inputs.sessions_since_listing is not None and inputs.sessions_since_listing < NEW_LISTING_SESSIONS else "unknown"
    trad_ids = () if variant == "raw" else (ASSUMPTIONS["tradable"], ASSUMPTIONS["band"], ASSUMPTIONS["limit_state"], ASSUMPTIONS["st"], ASSUMPTIONS["listing"])
    tradability = k.TradabilityEvidence(inputs.symbol, inputs.session, status, limit_state, "band", str(hi), str(lo), "unknown", listing_state, t_obs, t_avail,
                                        provenance(inputs.captured_at, trad_ids, "MODEL:halt_ledger+previous_close_band+open_print"), synthetic)
    price = k.PriceObservation(inputs.symbol, price_value, price_field, p_obs, p_avail, provenance(inputs.captured_at, price_ids, "daily_bar_cache.open"),
                               "contemporaneous" if variant == "raw" else "predeclared_assumption", synthetic, None if variant == "raw" else (price_ids[0] if price_ids else None))
    cap = capacity(k, inputs.symbol, inputs.session, order_quantity, capacity_variant, inputs.captured_at, synthetic)
    return r.AttemptEvidence(attempt_id, executed_at, inputs.session, "open_auction", tradability, price, cap)


def ex_date_flags(positions: list[dict[str, Any]], known_ex_dates: dict[str, list[str]]) -> list[dict[str, Any]]:
    """POST-HOC performance flag only: a closed/open position whose [entry_session, exit_session or last session] window
    contains a known ex-date is flagged; nothing is removed or re-decided (original availability of the notices is not
    established, so the flag cannot act before the trade)."""
    out = []
    for p in positions:
        dates = known_ex_dates.get(p["symbol"], [])
        inside = [d for d in dates if p["entry_session"] <= d <= p["last_session"]]
        out.append({**p, "known_ex_dates_in_window": inside, "adjustment_uncertainty": True, "flag": ASSUMPTIONS["ex_date_flag"] if inside else None})
    return out


__all__ = ["ASSUMPTIONS", "BOARD_RATIOS", "VARIANTS", "CAPACITY_VARIANTS", "FIXED_CAPACITY_SHARES", "CALENDAR_ASSUMED_AVAILABLE_AT", "OpenAttemptInputs",
           "board_by_code_prefix", "close_times", "open_times", "provenance", "assumed_band", "limit_state_from_open", "mark", "benchmark_level", "signal",
           "calendar", "decision_context", "execution_assumptions", "fee_schedule", "capacity", "attempt_evidence", "ex_date_flags"]
