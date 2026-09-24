"""Information-timing contract between order intents and daily-bar fill adjudication.

The production backtest works on daily bars. It used to size an open-time buy
with the same session's CLOSE, let intraday stop/take-profit proceeds fund
open-time buys, and judge price bands and capacity from the whole day's
high/low/amount. None of that was knowable at the open.

The contract below separates two things:

**Order intent** - committed before the session's open from information
available then: start-of-session cash, positions marked at their last CLOSED
bar (average cost when there is none), the pre-open position count, plus the
opening print as the reference price of a market-at-open order. Exits are
decided from closed bars (MA break, holding days) or placed as resting orders
(stop, take-profit) with trigger prices fixed pre-open. Nothing observed after
the open can change an intent, its quantity or its budget; proceeds of this
session's sales are not reused by this session's buys.

**Fill adjudication** - decided afterwards from the daily bar, under a named
policy:

* ``daily_bar_retrospective`` (default; the historical assumptions, now named):
  market-at-open orders are judged against the whole session's range for price
  bands and against the whole session's amount for capacity.
* ``pre_open_causal``: market-at-open orders are judged only against the
  opening print (price band) and the prior session's amount (capacity), so the
  fill itself is invariant to later prices in the session.

Resting stop/take-profit orders are necessarily adjudicated against the
session's high/low under both policies; the intraday path is unknown and the
result is labelled as such. Neither policy is qualified historical execution
evidence: fees are configured rates, capacity is a participation assumption,
price limits are an inferred-board signal threshold, and daily bars cannot
prove an auction fill.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from typing import Any

EXECUTION_CONTRACT_VERSION = "backtest_execution.v2"

FILL_POLICY_RETROSPECTIVE = "daily_bar_retrospective"
FILL_POLICY_PRE_OPEN = "pre_open_causal"
FILL_POLICIES = (FILL_POLICY_RETROSPECTIVE, FILL_POLICY_PRE_OPEN)

ORDER_MARKET_AT_OPEN = "market_at_open"
ORDER_RESTING_STOP = "resting_stop"
ORDER_RESTING_LIMIT = "resting_limit"

INTENT_CUTOFF = "before_session_open"

PRICE_BAND_SESSION_RANGE = "session_range"
PRICE_BAND_SESSION_OPEN = "session_open"
CAPACITY_SAME_SESSION = "same_session_amount"
CAPACITY_PRIOR_SESSION = "prior_session_amount"


@dataclass(frozen=True)
class OrderIntent:
    """An order as committed before the session opens. Immutable by construction."""

    session: str
    symbol: str
    side: str
    order_type: str
    reason: str
    requested_quantity: int
    reference_price: float
    trigger_price: float | None = None
    budget: float | None = None
    reserved_cash: float = 0.0
    information_cutoff: str = INTENT_CUTOFF
    sizing_inputs: dict[str, Any] = field(default_factory=dict)

    @property
    def intent_id(self) -> str:
        return f"{self.session}:{self.side}:{self.symbol}:{self.order_type}"

    def fingerprint(self) -> str:
        encoded = json.dumps(asdict(self), sort_keys=True, separators=(",", ":"), default=str)
        return hashlib.sha256(encoded.encode("utf-8")).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        return {**asdict(self), "intent_id": self.intent_id, "fingerprint": self.fingerprint()}


def adjudication_bases(fill_policy: str, order_type: str) -> dict[str, str]:
    """Which information a fill decision may use, per policy and order type."""

    if fill_policy not in FILL_POLICIES:
        raise ValueError(f"unknown fill policy: {fill_policy!r}")
    causal = fill_policy == FILL_POLICY_PRE_OPEN
    if order_type == ORDER_MARKET_AT_OPEN:
        return {
            "fill_basis": "opening_print",
            "price_band_basis": PRICE_BAND_SESSION_OPEN if causal else PRICE_BAND_SESSION_RANGE,
            "capacity_basis": CAPACITY_PRIOR_SESSION if causal else CAPACITY_SAME_SESSION,
        }
    return {
        "fill_basis": "resting_order_daily_range",
        "price_band_basis": PRICE_BAND_SESSION_RANGE,
        "capacity_basis": CAPACITY_PRIOR_SESSION if causal else CAPACITY_SAME_SESSION,
    }


def execution_contract(fill_policy: str, *, fundamentals_point_in_time: bool) -> dict[str, Any]:
    if fill_policy not in FILL_POLICIES:
        raise ValueError(f"unknown fill policy: {fill_policy!r}")
    causal = fill_policy == FILL_POLICY_PRE_OPEN
    return {
        "version": EXECUTION_CONTRACT_VERSION,
        "fill_policy": fill_policy,
        "intent_information_cutoff": INTENT_CUTOFF,
        "intent_inputs": [
            "start_of_session_cash",
            "positions_marked_at_last_closed_bar",
            "pre_open_position_count",
            "opening_print_for_market_at_open_prices",
            "closed_bar_exit_rules",
        ],
        "same_session_sale_proceeds_reused": False,
        "entry_budget_includes_estimated_fees": True,
        "market_at_open": adjudication_bases(fill_policy, ORDER_MARKET_AT_OPEN),
        "resting_orders": adjudication_bases(fill_policy, ORDER_RESTING_STOP),
        "market_at_open_fill_invariant_to_later_session_prices": causal,
        "resting_order_path": "daily_high_low_touch; intraday path unknown; stop precedes take-profit",
        "qualified_historical_execution": False,
        "fees": "configured commission (min 5 CNY) and sell stamp tax; not effective-dated tariffs",
        "capacity": "participation-rate assumption; not observed auction or intraday capacity",
        "price_limit_basis": "inferred-board signal threshold; ST and exchange band not verified",
        "fundamentals_point_in_time": fundamentals_point_in_time,
    }
