"""M4-02B deterministic synthetic policy orchestration over the frozen kernel (M4-01) and ledger (M4-02A).

Scope: a small stdlib-only, in-memory layer that turns injected, time-stamped evidence into explicit
decisions, sized intents, kernel attempts, ledger effects, exit/cooldown state, benchmark alignment and a
valuation / performance view.  Both frozen modules are **injected** (``PolicyEngine(kernel=..., ledger=...)``);
this file never imports ``app``, settings, a database, the filesystem, the network, a clock or randomness.
No optimization, ranking, training, universe expansion or historical read.

Causal boundaries
-----------------
* Every mark, signal, security status and benchmark observation carries ``symbol``, ``observed_at``,
  ``available_at``, ``source_ref`` and ``synthetic``.  A decision at ``decided_at`` may only consume items with
  ``observed_at <= decided_at`` and ``available_at <= decided_at``; anything else is refused explicitly.
* Valuation uses the eligible mark of the decision session (age ``<= max_mark_age_sessions`` on the injected
  calendar).  A held symbol without an eligible mark makes the valuation ``incomplete``; the position is kept and
  listed - never dropped, never valued at zero, cost or a later close.
* Buys are sized against explicit cash, per-position and gross-exposure limits from the *decision-time*
  valuation; rooms are reserved sequentially in a stable order so simultaneous intents cannot spend the same
  cash or exposure.  At execution the affordable quantity is re-checked against the reservation at the observed
  execution price (never a later close): a gap may downsize (whole lots) or cancel, never enlarge.
* Exits are decided on observed closes only; the fill is the next legal point through the frozen kernel at
  the legally observed price.  A bar merely touching a threshold never produces a fill.
* Cooldown starts only when an exit intent has actually closed the whole position; partial exits keep the
  residual and the pending remainder; unfilled / rejected / duplicate attempts never close holdings or reset
  cooldown.
* The benchmark is an injected index series aligned on decision sessions with the same evidence-time checks;
  a missing observation is ``missing`` (not zero); no interpolation; never traded.
* Delisting: a status is usable only when available; a later terminal status cannot remove earlier trades;
  a delisted holding stays on the books as an unresolved position with the precise limitation - no invented
  liquidation.  Hypothetical terminal scenarios are reported separately and never posted.

Statuses are distinct: decisions, intents (``pending`` / ``partially_filled`` / ``filled`` / ``unfilled_live`` /
``expired`` / ``rejected`` / ``cancelled``), attempts, fills and unresolved states.  All outputs carry
``review_only=True``, ``live_trading_enabled=False``, ``training_eligible=False``.
"""
from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import dataclass, replace
from datetime import datetime
from decimal import ROUND_CEILING, ROUND_FLOOR, ROUND_HALF_UP, Decimal, localcontext
from typing import Any

RISK_CONTRACT_VERSION = "0.1.0-draft"
RISK_NAMESPACE = "m4.risk"
CENT = Decimal("0.01")

INTENT_STATUSES = ("pending", "partially_filled", "filled", "unfilled_live", "expired", "rejected", "cancelled")
EXIT_REASONS = ("stop_loss", "profit_target", "max_holding")
SECURITY_STATUSES = ("listed", "suspended", "delisting_announced", "delisted")
REFUSAL_CODES = (
    "future_evidence", "stale_mark", "missing_mark", "inconsistent_evidence", "valuation_incomplete", "symbol_not_in_universe", "symbol_held",
    "symbol_pending_intent", "cooldown_active", "security_not_tradable", "insufficient_cash_or_room", "duplicate_signal", "benchmark_symbol",
)

_POLICY_SOURCE: dict[str, Any] = {
    "namespace": RISK_NAMESPACE, "contract_version": RISK_CONTRACT_VERSION,
    "kernel": {"module": "backend/app/research/m4_execution.py", "policy_hash": "9bea83482d545e6f39dd8eb70e89d674dd5d900378b596c243da8e122c273e62"},
    "ledger": {"module": "backend/app/research/m4_portfolio.py", "policy_hash": "633f78d987141b0e3dccad5d8e711b241a2eaf58b2a8dbe65e57603b5624d6f6"},
    "evidence_time": "observed_at <= decided_at and available_at <= decided_at for every mark/signal/status/benchmark item consumed by a decision; otherwise refused (future_evidence)",
    "valuation": {"mark": "eligible mark = latest mark of the symbol observed on a session with 0 <= session_age <= max_mark_age_sessions (calendar sessions), available by decided_at; "
                          "mark prices must be positive tick multiples and are re-spelled at the tick scale; benchmark levels are quantized to 0.01",
                  "missing": "held symbol without eligible mark -> valuation incomplete; position retained and listed; no zero/cost/later-close fallback",
                  "equity": "cash + sum(quantity x mark) over valued positions; gross_exposure = sum(quantity x mark); weight = value / equity"},
    "sizing": {"order": "signals processed in stable (symbol, signal_id) order; each reservation reduces the rooms of the next",
               "rooms": "position_room = max_position_weight x equity - existing value; portfolio_room = max_gross_exposure x equity - gross_exposure - reserved_exposure; "
                        "cash_room = cash - min_cash_reserve - reserved_cash; budget = min(rooms)",
               "quantity": "largest lot multiple q with estimated_cost(q, reserved_price) <= budget where reserved_price = ceil_tick(mark x (1 + slippage_rate)) and "
                           "estimated_cost = q x reserved_price + max(round(gross x buy_commission_rate), min_commission) + round(gross x transfer_fee_rate)",
               "zero": "q < min_buy_quantity -> zero-size decision with reason insufficient_cash_or_room; never a forced minimum lot",
               "limit_price": "buy ceil_tick(mark x (1 + max_gap_pct)); sell floor_tick(mark x (1 - max_gap_pct)); a fill beyond the limit is left unfilled by the kernel",
               "reservation": "budget reserved per intent; released on filled/expired/rejected/cancelled; retained (for the remainder) while pending/partially_filled/unfilled_live"},
    "execution_recheck": "at execution the affordable quantity is recomputed at the kernel's slipped fill price of the observed execution print against the reserved budget: "
                         "downsize to whole lots (gap_downsized) or cancel (gap_exceeds_budget); never enlarge; never uses a later close",
    "exits": {"reference": "entry_cost_reference = FIFO cost_remaining / quantity_remaining of the symbol's lots (fees included)",
              "rules": "stop_loss: mark <= ref x (1 - stop_loss_pct); profit_target: mark >= ref x (1 + profit_target_pct); max_holding: sessions_held >= max_holding_sessions",
              "priority": "policy.exit_priority (first matching reason wins); decisions on observed closes only; execution at the next legal point via the kernel",
              "partial": "a partial exit keeps the residual position and the pending remainder; cooldown starts only when the position quantity reaches zero through exit fills",
              "cooldown": "re-entry allowed at decision sessions with index(decision_session) - index(exit_session) >= cooldown_sessions (calendar sessions)"},
    "benchmark": {"series": "injected index levels; symbol role benchmark; never traded", "alignment": "levels on exactly the start/end decision sessions, available by as_of",
                  "missing": "missing observation -> status missing (not zero); no interpolation or lookahead"},
    "delisting": {"status_at": "latest security status with available_at <= decided_at", "announced": "no new buys; holdings kept",
                  "delisted": "holding retained as unresolved; valuation/performance incomplete; no liquidation posted; hypothetical terminal scenarios reported separately"},
    "identities": {"decision_hash": "sha256(canonical decision record)", "chain": "record_hash = sha256(previous + canonical record)"},
    "flags": {"review_only": True, "live_trading_enabled": False, "training_eligible": False, "M4_complete": False},
    "not_implemented_here": ["signal generation / ranking", "optimization or tuning", "historical data adapters", "corporate actions", "intraday ordering inference"],
}


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False, default=_default)


def _default(value: Any) -> Any:
    if isinstance(value, Decimal):
        return str(value)
    raise TypeError(f"unserializable {type(value).__name__}")


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


RISK_POLICY: dict[str, Any] = json.loads(canonical_json(_POLICY_SOURCE))
RISK_POLICY_HASH = sha256_text(canonical_json(_POLICY_SOURCE))


class RiskInputError(ValueError):
    def __init__(self, code: str, detail: str) -> None:
        super().__init__(f"{code}: {detail}")
        self.code, self.detail = code, detail


# ---------------------------------------------------------------------- evidence dataclasses
@dataclass(frozen=True)
class Mark:
    symbol: str
    price: Any
    observed_at: str
    available_at: str
    source_ref: str
    synthetic: bool


@dataclass(frozen=True)
class Signal:
    signal_id: str
    symbol: str
    side: str
    observed_at: str
    available_at: str
    source_ref: str
    synthetic: bool


@dataclass(frozen=True)
class SecurityStatus:
    symbol: str
    status: str
    observed_at: str
    available_at: str
    source_ref: str
    synthetic: bool


@dataclass(frozen=True)
class BenchmarkObservation:
    symbol: str
    level: Any
    observed_at: str
    available_at: str
    source_ref: str
    synthetic: bool


@dataclass(frozen=True)
class RiskPolicy:
    """Explicit caller-supplied parameters (hypothetical; no tuning)."""

    policy_id: str
    provenance: str
    max_position_weight: Any
    max_gross_exposure: Any
    min_cash_reserve: Any
    stop_loss_pct: Any
    profit_target_pct: Any            # None disables
    max_holding_sessions: int
    cooldown_sessions: int
    max_mark_age_sessions: int
    max_gap_pct: Any
    intent_expiry_sessions: int
    exit_priority: tuple[str, ...]

    def validated(self) -> "RiskPolicy":
        for name in ("policy_id", "provenance"):
            _str(getattr(self, name), name)
        for name, hi in (("max_position_weight", "1"), ("max_gross_exposure", "1"), ("stop_loss_pct", "1"), ("max_gap_pct", "0.5")):
            d = _dec(getattr(self, name), name)
            if not (Decimal(0) < d <= Decimal(hi)):
                raise RiskInputError("invalid_policy", f"{name} must be in (0, {hi}], got {d}")
        if _dec(self.min_cash_reserve, "min_cash_reserve") < 0:
            raise RiskInputError("invalid_policy", "min_cash_reserve must be >= 0")
        if self.profit_target_pct is not None and _dec(self.profit_target_pct, "profit_target_pct") <= 0:
            raise RiskInputError("invalid_policy", "profit_target_pct must be > 0 or None")
        for name, minimum in (("max_holding_sessions", 1), ("cooldown_sessions", 0), ("max_mark_age_sessions", 0), ("intent_expiry_sessions", 1)):
            _int(getattr(self, name), name, minimum)
        if not isinstance(self.exit_priority, tuple) or not self.exit_priority or any(r not in EXIT_REASONS for r in self.exit_priority) or len(set(self.exit_priority)) != len(self.exit_priority):
            raise RiskInputError("invalid_policy", f"exit_priority must be a non-empty tuple of distinct {EXIT_REASONS}")
        return self


@dataclass(frozen=True)
class UniverseMember:
    symbol: str
    role: str
    board: str
    listing_evidence_ref: str


@dataclass(frozen=True)
class DecisionContext:
    """What a decision may use besides evidence: the session it is taken after, the instant, the calendar and the
    hypothetical execution assumptions / fees that will be handed to the frozen kernel."""

    decision_session: str
    decided_at: str
    calendar: Any                 # kernel.SessionCalendar
    fee_schedule: Any             # kernel.FeeSchedule
    assumptions: Any              # kernel.ExecutionAssumptions


@dataclass(frozen=True)
class AttemptEvidence:
    """Attempt-time execution evidence for one intent (kernel objects), plus the attempt instant/phase."""

    attempt_id: str
    executed_at: str
    session: str
    phase: str
    tradability: Any
    price: Any
    capacity: Any


class _Refuse(Exception):
    def __init__(self, code: str, detail: str, **extra: Any) -> None:
        super().__init__(code)
        self.code, self.detail, self.extra = code, detail, extra


class PolicyEngine:
    """Deterministic policy orchestration.  ``kernel`` and ``ledger_module`` are the injected frozen modules;
    ``ledger`` is a ``PortfolioLedger`` instance built by the caller."""

    def __init__(self, *, kernel: Any, ledger_module: Any, ledger: Any, policy: RiskPolicy, universe: tuple[UniverseMember, ...], benchmark_symbol: str,
                 engine_id: str) -> None:
        for attr in ("execute", "ExecutionRequest", "Decision", "Order", "Instrument", "InputAvailability", "ARITHMETIC_CONTEXT", "POLICY_HASH", "_record"):
            if not hasattr(kernel, attr):
                raise RiskInputError("invalid_kernel", f"kernel lacks {attr}")
        for attr in ("AttemptEvent", "LEDGER_POLICY_HASH"):
            if not hasattr(ledger_module, attr):
                raise RiskInputError("invalid_ledger_module", f"ledger module lacks {attr}")
        if kernel.POLICY_HASH != RISK_POLICY["kernel"]["policy_hash"] or ledger_module.LEDGER_POLICY_HASH != RISK_POLICY["ledger"]["policy_hash"]:
            raise RiskInputError("frozen_policy_mismatch", "injected kernel/ledger policy hashes differ from the frozen ones this layer was built on")
        self.kernel, self.lm, self.ledger = kernel, ledger_module, ledger
        self.policy = policy.validated()
        self.engine_id = _str(engine_id, "engine_id")
        self.benchmark_symbol = _str(benchmark_symbol, "benchmark_symbol")
        self.universe: dict[str, UniverseMember] = {}
        for m in universe:
            if not isinstance(m, UniverseMember) or m.role != "stock":
                raise RiskInputError("invalid_universe", "universe members must be UniverseMember with role stock")
            if m.symbol == self.benchmark_symbol:
                raise RiskInputError("invalid_universe", "the benchmark symbol cannot be a tradable universe member")
            self.universe[m.symbol] = m
        self._state: dict[str, Any] = {"intents": {}, "reservations": {}, "exit_sessions": {}, "entry_sessions": {}, "sequence": 0, "last_decided_at": None,
                                       "decisions": 0, "attempts": 0}
        self._records: list[dict[str, Any]] = []
        self._hash = sha256_text(canonical_json({"engine_id": self.engine_id, "policy": RISK_POLICY_HASH, "risk_policy": _rec(self.policy)}))
        self.genesis_hash = self._hash

    # ------------------------------------------------------------------ views (detached)
    @property
    def records(self) -> tuple[dict[str, Any], ...]:
        return tuple(copy.deepcopy(r) for r in self._records)

    @property
    def chain_hash(self) -> str:
        return self._hash

    def intents(self) -> dict[str, dict[str, Any]]:
        return copy.deepcopy(self._state["intents"])

    def reservations(self) -> dict[str, Any]:
        st = self._state
        with localcontext(self.kernel.ARITHMETIC_CONTEXT):
            return {"by_intent": copy.deepcopy(st["reservations"]),
                    "reserved_cash": _ms(sum((Decimal(r["budget"]) for r in st["reservations"].values()), Decimal("0.00"))),
                    "reserved_exposure": _ms(sum((Decimal(r["budget"]) for r in st["reservations"].values()), Decimal("0.00")))}

    # ------------------------------------------------------------------ evidence helpers
    def _eligible(self, items, decided_at: datetime, what: str) -> tuple[list, list[dict[str, Any]]]:
        ok, refused = [], []
        for item in items:
            try:
                if _inst(item.observed_at) > decided_at or _inst(item.available_at) > decided_at:
                    refused.append({"code": "future_evidence", "what": what, "symbol": item.symbol, "observed_at": item.observed_at, "available_at": item.available_at})
                    continue
                if _inst(item.available_at) < _inst(item.observed_at):
                    refused.append({"code": "inconsistent_evidence", "what": what, "symbol": item.symbol, "detail": "available before observed"})
                    continue
                if not isinstance(item.synthetic, bool) or not isinstance(item.source_ref, str) or not item.source_ref:
                    refused.append({"code": "inconsistent_evidence", "what": what, "symbol": item.symbol, "detail": "missing provenance/synthetic flag"})
                    continue
                ok.append(item)
            except (ValueError, TypeError) as exc:
                refused.append({"code": "inconsistent_evidence", "what": what, "symbol": getattr(item, "symbol", None), "detail": str(exc)})
        return ok, refused

    def _mark_for(self, symbol: str, marks: list, ctx: DecisionContext, index: dict[str, int]) -> tuple[Mark | None, dict[str, Any] | None]:
        """Latest eligible mark within the declared age; returns (mark, refusal).  Mark prices are tick aligned and
        re-spelled at the tick scale so numeric spellings cannot change records."""
        candidates = []
        tick = _tick(ctx)
        for m in marks:
            if m.symbol != symbol:
                continue
            price = _dec(m.price, "mark price")
            if price <= 0 or (price / tick) != (price / tick).to_integral_value():
                return None, {"code": "inconsistent_evidence", "symbol": symbol, "detail": f"mark price {price} is not a positive multiple of tick {tick}"}
            m = replace(m, price=price.quantize(tick))
            session = ctx.calendar.local_date(_inst(m.observed_at))
            if session not in index:
                continue
            age = index[ctx.decision_session] - index[session]
            if age < 0:
                continue
            candidates.append((age, m.observed_at, m))
        if not candidates:
            return None, {"code": "missing_mark", "symbol": symbol}
        candidates.sort(key=lambda c: (c[0], c[1]))
        age, observed_at, mark = candidates[0]
        conflicting = {str(c[2].price) for c in candidates if c[0] == age and c[1] == observed_at}
        if len(conflicting) > 1:
            return None, {"code": "inconsistent_evidence", "symbol": symbol, "detail": f"conflicting marks at {observed_at}: {sorted(conflicting)}"}
        if age > self.policy.max_mark_age_sessions:
            return None, {"code": "stale_mark", "symbol": symbol, "age_sessions": age, "max_age": self.policy.max_mark_age_sessions, "observed_at": mark.observed_at}
        return mark, None

    def _status_at(self, symbol: str, statuses: list) -> str:
        rows = sorted((s for s in statuses if s.symbol == symbol), key=lambda s: (s.observed_at, s.available_at))
        return rows[-1].status if rows else "listed"

    # ------------------------------------------------------------------ decide
    def decide(self, decision_id: str, ctx: DecisionContext, *, marks: tuple = (), signals: tuple = (), statuses: tuple = (), benchmark: tuple = ()) -> dict[str, Any]:
        """One decision after the close of ``ctx.decision_session``: valuation, exits, sized entries, benchmark alignment."""
        with localcontext(self.kernel.ARITHMETIC_CONTEXT):
            work = copy.deepcopy(self._state)
            record: dict[str, Any] = {"schema": f"{RISK_NAMESPACE}.decision.v1", "engine_id": self.engine_id, "decision_id": decision_id, "kind": "decision",
                                      "session": ctx.decision_session, "decided_at": ctx.decided_at, "refusals": [], "chain_hash_before": self._hash}
            try:
                _str(decision_id, "decision_id")
                ctx.calendar.validated(); ctx.fee_schedule.validated(); ctx.assumptions.validated()
                decided_at = _inst(ctx.decided_at)
                index = ctx.calendar.index()
                if ctx.decision_session not in index:
                    raise _Refuse("inconsistent_evidence", f"decision session {ctx.decision_session} not in the calendar")
                if decided_at < ctx.calendar.close_at(ctx.decision_session):
                    raise _Refuse("inconsistent_evidence", f"decided_at {ctx.decided_at} precedes the close of {ctx.decision_session}")
                if work["last_decided_at"] is not None and decided_at < _inst(work["last_decided_at"]):
                    raise _Refuse("inconsistent_evidence", f"decided_at {ctx.decided_at} precedes the previous decision {work['last_decided_at']}")
                if decision_id in {r["decision_id"] for r in self._records if r["kind"] == "decision"}:
                    raise _Refuse("duplicate_signal", f"decision_id {decision_id} already recorded")
                ok_marks, refused = self._eligible(list(marks), decided_at, "mark")
                ok_signals, r2 = self._eligible(list(signals), decided_at, "signal")
                ok_status, r3 = self._eligible(list(statuses), decided_at, "status")
                ok_bench, r4 = self._eligible(list(benchmark), decided_at, "benchmark")
                record["refusals"].extend(refused + r2 + r3 + r4)
                # ---- valuation
                snap = self.ledger.snapshot()
                cash = Decimal(snap["cash"])
                positions, incomplete, gross = {}, [], Decimal("0.00")
                for symbol, qty in sorted(snap["positions"].items()):
                    mark, refusal = self._mark_for(symbol, ok_marks, ctx, index)
                    status = self._status_at(symbol, ok_status)
                    lots = snap["lots"][symbol]
                    cost_remaining = sum((Decimal(l["cost_remaining"]) for l in lots if l["quantity_remaining"] > 0), Decimal("0.00"))
                    entry_ref = (cost_remaining / Decimal(qty)) if qty else None
                    entry_session = min(l["acquired_session"] for l in lots if l["quantity_remaining"] > 0)
                    row = {"quantity": qty, "status": status, "entry_cost_reference": str(entry_ref.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)) if entry_ref is not None else None,
                           "entry_session": entry_session, "sessions_held": index[ctx.decision_session] - index[entry_session] if entry_session in index else None}
                    if mark is None or status == "delisted":
                        row.update({"mark": None, "value": None, "weight": None, "unresolved_reason": refusal or {"code": "security_not_tradable", "status": status}})
                        incomplete.append(symbol)
                    else:
                        price = _dec(mark.price, "mark price")
                        value = _cents(price * Decimal(qty))
                        gross += value
                        row.update({"mark": str(price), "mark_observed_at": mark.observed_at, "mark_source_ref": mark.source_ref, "value": _ms(value), "weight": None})
                    positions[symbol] = row
                complete = not incomplete
                equity = cash + gross if complete else None
                if complete:
                    for row in positions.values():
                        row["weight"] = str((Decimal(row["value"]) / equity).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)) if equity else None
                valuation = {"complete": complete, "cash": _ms(cash), "gross_exposure": _ms(gross) if complete else None, "equity": _ms(equity) if complete else None,
                             "gross_weight": str((gross / equity).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)) if complete and equity else None,
                             "positions": positions, "incomplete_symbols": incomplete}
                record["valuation"] = valuation
                # ---- exits (observed closes only; execution at the next legal point via the kernel)
                exits = []
                for symbol, row in positions.items():
                    if row["mark"] is None:
                        exits.append({"symbol": symbol, "decision": "unresolved", "reason": row["unresolved_reason"]})
                        continue
                    pending = [i for i in work["intents"].values() if i["symbol"] == symbol and i["side"] == "sell" and i["status"] in ("pending", "partially_filled", "unfilled_live")]
                    if pending:
                        exits.append({"symbol": symbol, "decision": "exit_pending", "intent_id": pending[0]["intent_id"]})
                        continue
                    ref, price = Decimal(row["entry_cost_reference"]), Decimal(row["mark"])
                    triggered = {}
                    triggered["stop_loss"] = price <= ref * (Decimal(1) - _dec(self.policy.stop_loss_pct, "stop"))
                    triggered["profit_target"] = self.policy.profit_target_pct is not None and price >= ref * (Decimal(1) + _dec(self.policy.profit_target_pct, "target"))
                    triggered["max_holding"] = row["sessions_held"] is not None and row["sessions_held"] >= self.policy.max_holding_sessions
                    reason = next((r for r in self.policy.exit_priority if triggered.get(r)), None)
                    if reason is None:
                        exits.append({"symbol": symbol, "decision": "hold", "checks": {k: bool(v) for k, v in triggered.items()}})
                        continue
                    limit = _round_tick(price * (Decimal(1) - _dec(self.policy.max_gap_pct, "gap")), _tick(ctx), "down")
                    intent = self._new_intent(work, decision_id, ctx, symbol, "sell", row["quantity"], limit, reason, index, mark_ref=row["mark_source_ref"], mark_at=row["mark_observed_at"])
                    exits.append({"symbol": symbol, "decision": "exit", "reason": reason, "checks": {k: bool(v) for k, v in triggered.items()}, "intent_id": intent["intent_id"],
                                  "quantity": row["quantity"], "limit_price": str(limit)})
                record["exits"] = exits
                # ---- entries: stable order, sequential reservation
                entries = []
                seen_signals = set()
                reserved_cash = sum((Decimal(r["budget"]) for r in work["reservations"].values()), Decimal("0.00"))
                reserved_exposure = reserved_cash
                for sig in sorted(ok_signals, key=lambda s: (s.symbol, s.signal_id)):
                    entry: dict[str, Any] = {"signal_id": sig.signal_id, "symbol": sig.symbol, "side": sig.side}
                    try:
                        if sig.side != "buy":
                            raise _Refuse("inconsistent_evidence", "only buy signals are sized; exits come from the policy")
                        if sig.signal_id in seen_signals:
                            raise _Refuse("duplicate_signal", "same signal_id twice in one decision")
                        seen_signals.add(sig.signal_id)
                        if sig.symbol == self.benchmark_symbol:
                            raise _Refuse("benchmark_symbol", "an index is never traded through the stock ledger")
                        if sig.symbol not in self.universe:
                            raise _Refuse("symbol_not_in_universe", sig.symbol)
                        if not complete:
                            raise _Refuse("valuation_incomplete", f"held positions without eligible marks: {incomplete}")
                        if sig.symbol in snap["positions"]:
                            raise _Refuse("symbol_held", f"{sig.symbol} already held ({snap['positions'][sig.symbol]} shares)")
                        if any(i["symbol"] == sig.symbol and i["status"] in ("pending", "partially_filled", "unfilled_live") for i in work["intents"].values()):
                            raise _Refuse("symbol_pending_intent", f"{sig.symbol} has a live intent")
                        exit_session = work["exit_sessions"].get(sig.symbol)
                        if exit_session is not None and index[ctx.decision_session] - index[exit_session] < self.policy.cooldown_sessions:
                            raise _Refuse("cooldown_active", f"exited {exit_session}; {index[ctx.decision_session] - index[exit_session]} of {self.policy.cooldown_sessions} cooldown sessions elapsed",
                                          exit_session=exit_session)
                        status = self._status_at(sig.symbol, ok_status)
                        if status != "listed":
                            raise _Refuse("security_not_tradable", f"status {status}", status=status)
                        mark, refusal = self._mark_for(sig.symbol, ok_marks, ctx, index)
                        if mark is None:
                            raise _Refuse(refusal["code"], canonical_json(refusal))
                        price = _dec(mark.price, "mark price")
                        position_room = _dec(self.policy.max_position_weight, "w") * equity
                        portfolio_room = _dec(self.policy.max_gross_exposure, "g") * equity - gross - reserved_exposure
                        cash_room = cash - _dec(self.policy.min_cash_reserve, "reserve") - reserved_cash
                        budget = _floor_cents(min(position_room, portfolio_room, cash_room))
                        reserved_price = _round_tick(price * (Decimal(1) + _dec(ctx.assumptions.slippage_rate, "slip")), _tick(ctx), "up")
                        quantity, estimate = _affordable(budget, reserved_price, ctx, sizing_cap=None)
                        rooms = {"position_room": _ms(position_room), "portfolio_room": _ms(portfolio_room), "cash_room": _ms(cash_room), "budget": _ms(budget),
                                 "reserved_price": str(reserved_price), "mark": str(price)}
                        if quantity <= 0:
                            entries.append({**entry, "decision": "zero_size", "reason": "insufficient_cash_or_room", "rooms": rooms, "estimated_cost_one_lot": _ms(_estimate(ctx.assumptions.lot_policy.min_buy_quantity, reserved_price, ctx))})
                            continue
                        limit = _round_tick(price * (Decimal(1) + _dec(self.policy.max_gap_pct, "gap")), _tick(ctx), "up")
                        intent = self._new_intent(work, decision_id, ctx, sig.symbol, "buy", quantity, limit, f"signal:{sig.signal_id}", index, mark_ref=mark.source_ref,
                                                  mark_at=mark.observed_at, budget=budget, estimated_cost=estimate)
                        reserved_cash += budget
                        reserved_exposure += budget
                        entries.append({**entry, "decision": "buy", "intent_id": intent["intent_id"], "quantity": quantity, "limit_price": str(limit), "rooms": rooms,
                                        "estimated_cost": _ms(estimate), "reserved_budget": _ms(budget)})
                    except _Refuse as exc:
                        entries.append({**entry, "decision": "refused", "reason": exc.code, "detail": exc.detail, **exc.extra})
                record["entries"] = entries
                # ---- benchmark alignment (evidence-time checked; missing is not zero)
                record["benchmark"] = self._benchmark_level(ok_bench, ctx, index)
                work["last_decided_at"] = ctx.decided_at
                work["decisions"] += 1
                record["reservations_after"] = {"reserved_cash": _ms(reserved_cash), "reserved_exposure": _ms(reserved_exposure)}
                record["status"] = "decided"
                self._state = work
            except _Refuse as exc:
                record["status"] = "refused"
                record["refusals"].append({"code": exc.code, "detail": exc.detail, **exc.extra})
            return self._commit(record)

    def _benchmark_level(self, observations: list, ctx: DecisionContext, index: dict[str, int]) -> dict[str, Any]:
        rows = [b for b in observations if b.symbol == self.benchmark_symbol and ctx.calendar.local_date(_inst(b.observed_at)) == ctx.decision_session]
        if not rows:
            return {"symbol": self.benchmark_symbol, "session": ctx.decision_session, "status": "missing", "level": None}
        rows.sort(key=lambda b: b.observed_at)
        b = rows[-1]
        return {"symbol": self.benchmark_symbol, "session": ctx.decision_session, "status": "observed", "level": _ms(_dec(b.level, "level")), "observed_at": b.observed_at,
                "available_at": b.available_at, "source_ref": b.source_ref}

    def _new_intent(self, work, decision_id, ctx, symbol, side, quantity, limit, reason, index, *, mark_ref, mark_at, budget=None, estimated_cost=None) -> dict[str, Any]:
        next_session = ctx.calendar.sessions[index[ctx.decision_session] + 1] if index[ctx.decision_session] + 1 < len(ctx.calendar.sessions) else None
        if next_session is None:
            raise _Refuse("inconsistent_evidence", "no session after the decision session in the injected calendar")
        intent_id = f"{decision_id}:{side}:{symbol}"
        if intent_id in work["intents"]:
            raise _Refuse("duplicate_signal", f"intent {intent_id} already exists")
        intent = {"intent_id": intent_id, "decision_id": decision_id, "symbol": symbol, "side": side, "quantity": quantity, "remaining": quantity, "filled": 0,
                  "limit_price": str(limit), "reason": reason, "status": "pending", "decision_session": ctx.decision_session, "decided_at": ctx.decided_at,
                  "eligible_from": ctx.calendar.open_at(next_session).isoformat(), "eligible_session": next_session, "expiry_sessions": self.policy.intent_expiry_sessions,
                  "mark_source_ref": mark_ref, "mark_observed_at": mark_at, "attempts": [], "budget": _ms(budget) if budget is not None else None,
                  "estimated_cost": _ms(estimated_cost) if estimated_cost is not None else None}
        work["intents"][intent_id] = intent
        if budget is not None:
            work["reservations"][intent_id] = {"symbol": symbol, "budget": _ms(budget), "kind": "buy_cash_and_exposure"}
        return intent

    # ------------------------------------------------------------------ execute
    def execute(self, intent_id: str, ctx: DecisionContext, evidence: AttemptEvidence) -> dict[str, Any]:
        """Attempt one intent through the frozen kernel/ledger with attempt-time evidence; atomic on this layer."""
        with localcontext(self.kernel.ARITHMETIC_CONTEXT):
            work = copy.deepcopy(self._state)
            record: dict[str, Any] = {"schema": f"{RISK_NAMESPACE}.attempt.v1", "engine_id": self.engine_id, "kind": "attempt", "intent_id": intent_id,
                                      "attempt_id": getattr(evidence, "attempt_id", None), "executed_at": getattr(evidence, "executed_at", None), "chain_hash_before": self._hash}
            try:
                intent = work["intents"].get(intent_id)
                if intent is None:
                    raise _Refuse("inconsistent_evidence", f"unknown intent {intent_id}")
                if intent["status"] not in ("pending", "partially_filled", "unfilled_live"):
                    raise _Refuse("inconsistent_evidence", f"intent {intent_id} is {intent['status']}; no further attempts")
                if not isinstance(evidence, AttemptEvidence):
                    raise _Refuse("inconsistent_evidence", "evidence must be AttemptEvidence")
                executed_at = _inst(evidence.executed_at)
                if any(a["attempt_id"] == evidence.attempt_id for a in intent["attempts"]):
                    record.update({"status": "duplicate", "detail": f"attempt {evidence.attempt_id} already recorded for {intent_id}; no ledger call, no holding/cooldown/reservation change"})
                    return self._commit(record)
                quantity = intent["remaining"]
                gap_note = None
                if intent["side"] == "buy":
                    # re-check the affordable quantity at the observed execution print (kernel slippage applied), against the reservation only
                    observed = _dec(evidence.price.price, "execution price").quantize(_tick(ctx))
                    fill_price = _round_tick(observed * (Decimal(1) + _dec(ctx.assumptions.slippage_rate, "slip")), _tick(ctx), "up")
                    budget = Decimal(work["reservations"][intent_id]["budget"])
                    affordable, estimate = _affordable(budget, fill_price, ctx, sizing_cap=quantity)
                    if affordable <= 0:
                        intent["status"] = "cancelled"
                        intent["attempts"].append({"attempt_id": evidence.attempt_id, "executed_at": evidence.executed_at, "outcome": "cancelled_gap_exceeds_budget",
                                                   "observed_price": str(observed), "fill_price_estimate": str(fill_price), "budget": _ms(budget)})
                        work["reservations"].pop(intent_id, None)
                        record.update({"status": "cancelled", "reason": "gap_exceeds_budget", "observed_price": str(observed), "fill_price_estimate": str(fill_price), "budget": _ms(budget)})
                        work["attempts"] += 1
                        self._state = work
                        return self._commit(record)
                    if affordable < quantity:
                        gap_note = {"code": "gap_downsized", "from": quantity, "to": affordable, "observed_price": str(observed), "fill_price_estimate": str(fill_price),
                                    "estimated_cost": _ms(estimate), "budget": _ms(budget)}
                        quantity = affordable
                member = self.universe[intent["symbol"]]
                k = self.kernel
                req = k.ExecutionRequest(
                    decision=k.Decision(intent["decision_id"] + ":" + intent["symbol"], intent["symbol"], intent["side"], intent["decision_session"], intent["decided_at"],
                                        (k.InputAvailability("valuation_mark", intent["mark_observed_at"], intent["mark_source_ref"]),), f"{self.policy.policy_id}:{intent['reason']}"),
                    order=k.Order(intent_id, intent["decision_id"] + ":" + intent["symbol"], intent["symbol"], intent["side"], quantity, intent["limit_price"], intent["decided_at"],
                                  intent["eligible_from"], intent["expiry_sessions"], evidence.phase),
                    instrument=k.Instrument(member.symbol, "stock", member.board, member.listing_evidence_ref, ctx.calendar.source_ref, True),
                    calendar=ctx.calendar, tradability=evidence.tradability, price=evidence.price,
                    account=self.ledger.account_state(evidence.executed_at, intent["symbol"]), fee_schedule=ctx.fee_schedule, assumptions=ctx.assumptions,
                    attempt=k.ExecutionAttempt(evidence.attempt_id, evidence.executed_at, evidence.session, evidence.phase), capacity=evidence.capacity)
                work["sequence"] += 1
                event = self.lm.AttemptEvent(f"{intent_id}:{evidence.attempt_id}", work["sequence"], req)
                ledger_record = self.ledger.apply(event)                       # the ledger is itself atomic; its audit record is kept verbatim
                kstatus = (ledger_record.get("kernel") or {}).get("status")
                outcome = {"attempt_id": evidence.attempt_id, "executed_at": evidence.executed_at, "ledger_status": ledger_record["status"], "kernel_status": kstatus,
                           "committed": ledger_record["committed"], "quantity_attempted": quantity, "gap": gap_note,
                           "ledger_event_record_hash": ledger_record["event_record_hash"], "reasons": ledger_record["reasons"]}
                if ledger_record["status"] == "applied":
                    filled = ledger_record["effects"]["filled_quantity"]
                    intent["filled"] += filled
                    intent["remaining"] = quantity - filled if gap_note is None else quantity - filled
                    if gap_note is not None:
                        intent["quantity"] = intent["filled"] + intent["remaining"]
                    outcome.update({"filled_quantity": filled, "fill_price": ledger_record["effects"]["fill_price"], "fees": ledger_record["effects"]["fees"],
                                    "cash_after": ledger_record["effects"]["cash_after"]})
                    live = ledger_record["order"]["live"]
                    if intent["remaining"] == 0:
                        intent["status"] = "filled"
                        work["reservations"].pop(intent_id, None)
                    else:
                        intent["status"] = "partially_filled" if live else "expired"
                        if not live:
                            work["reservations"].pop(intent_id, None)
                    if intent["side"] == "buy":
                        work["entry_sessions"][intent["symbol"]] = ledger_record["effects"]["lot_created"]["acquired_session"]
                    elif self.ledger.positions().get(intent["symbol"], 0) == 0:
                        work["exit_sessions"][intent["symbol"]] = ledger_record["effects"]["sale"]["session"]     # cooldown starts on the actual full exit
                        outcome["cooldown_started_session"] = ledger_record["effects"]["sale"]["session"]
                elif ledger_record["status"] == "no_effect" and ledger_record["committed"]:
                    intent["status"] = "unfilled_live" if ledger_record["order"]["live"] else "expired"
                    if intent["status"] == "expired":
                        work["reservations"].pop(intent_id, None)
                elif ledger_record["status"] == "no_effect":                  # kernel rejected: nothing happened; intent stays as it was
                    work["sequence"] -= 1
                    outcome["note"] = "kernel rejected the attempt; intent unchanged; reservation retained"
                elif ledger_record["status"] == "skipped_duplicate":
                    work["sequence"] -= 1
                    outcome["note"] = "duplicate attempt; no effect on holdings, cooldown or reservation"
                else:                                                          # ledger rejected: nothing committed there; record and keep the intent
                    work["sequence"] -= 1
                    outcome["note"] = "ledger rejected the attempt before commit; intent unchanged"
                intent["attempts"].append(outcome)
                work["attempts"] += 1
                record.update({"status": intent["status"], "outcome": outcome, "ledger_record": ledger_record})
                self._state = work
            except _Refuse as exc:
                record.update({"status": "refused", "reason": exc.code, "detail": exc.detail, **exc.extra})
            return self._commit(record)

    def cancel(self, intent_id: str, reason: str) -> dict[str, Any]:
        with localcontext(self.kernel.ARITHMETIC_CONTEXT):
            work = copy.deepcopy(self._state)
            record = {"schema": f"{RISK_NAMESPACE}.cancel.v1", "engine_id": self.engine_id, "kind": "cancel", "intent_id": intent_id, "reason": reason, "chain_hash_before": self._hash}
            intent = work["intents"].get(intent_id)
            if intent is None or intent["status"] not in ("pending", "partially_filled", "unfilled_live"):
                record["status"] = "refused"
                record["detail"] = "unknown intent or not cancellable"
                return self._commit(record)
            intent["status"] = "cancelled"
            work["reservations"].pop(intent_id, None)
            record["status"] = "cancelled"
            record["released_reservation"] = intent.get("budget")
            self._state = work
            return self._commit(record)

    # ------------------------------------------------------------------ benchmark and performance
    def benchmark_return(self, start_session: str, end_session: str, observations: tuple, as_of: str, calendar: Any) -> dict[str, Any]:
        with localcontext(self.kernel.ARITHMETIC_CONTEXT):
            at = _inst(as_of)
            ok, refused = self._eligible(list(observations), at, "benchmark")
            index = calendar.index()
            out = {"symbol": self.benchmark_symbol, "start_session": start_session, "end_session": end_session, "as_of": as_of, "refusals": refused}
            levels = {}
            for session in (start_session, end_session):
                rows = [b for b in ok if b.symbol == self.benchmark_symbol and calendar.local_date(_inst(b.observed_at)) == session]
                levels[session] = _ms(_dec(sorted(rows, key=lambda b: b.observed_at)[-1].level, "level")) if rows else None
            out["levels"] = levels
            if start_session not in index or end_session not in index or index[end_session] < index[start_session]:
                out.update({"status": "invalid_horizon", "return": None})
            elif levels[start_session] is None or levels[end_session] is None:
                out.update({"status": "missing", "return": None, "note": "a missing benchmark observation is not a zero return; no interpolation"})
            else:
                ratio = Decimal(levels[end_session]) / Decimal(levels[start_session]) - Decimal(1)
                out.update({"status": "observed", "return": str(ratio.quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP))})
            return out

    def performance(self, ctx: DecisionContext, *, marks: tuple = (), statuses: tuple = (), benchmark: tuple = (), start_session: str, initial_cash: Any,
                    hypothetical_terminal_marks: tuple = ()) -> dict[str, Any]:
        """Valuation-based performance at ``ctx.decision_session`` close.  Incomplete when any holding lacks an eligible mark or is delisted;
        hypothetical terminal scenarios are reported separately and never posted."""
        with localcontext(self.kernel.ARITHMETIC_CONTEXT):
            decided_at = _inst(ctx.decided_at)
            ok_marks, refused = self._eligible(list(marks), decided_at, "mark")
            ok_status, r2 = self._eligible(list(statuses), decided_at, "status")
            index = ctx.calendar.index()
            snap = self.ledger.snapshot()
            cash = Decimal(snap["cash"])
            rows, unresolved, gross = {}, [], Decimal("0.00")
            for symbol, qty in sorted(snap["positions"].items()):
                mark, refusal = self._mark_for(symbol, ok_marks, ctx, index)
                status = self._status_at(symbol, ok_status)
                if mark is None or status == "delisted":
                    reason = refusal or {"code": "security_not_tradable", "status": status}
                    limitation = ("frozen contracts carry no verified executable exit, settlement or corporate-action support for a delisted holding; "
                                  "the position is retained unresolved and no liquidation cash is posted") if status == "delisted" else "no eligible mark at this session"
                    rows[symbol] = {"quantity": qty, "status": status, "value": None, "unresolved_reason": reason, "limitation": limitation}
                    unresolved.append(symbol)
                else:
                    value = _cents(_dec(mark.price, "mark") * Decimal(qty))
                    gross += value
                    rows[symbol] = {"quantity": qty, "status": status, "mark": str(mark.price), "value": _ms(value)}
            complete = not unresolved
            initial = _cents(_dec(initial_cash, "initial_cash"))
            equity = cash + gross if complete else None
            report = {"schema": f"{RISK_NAMESPACE}.performance.v1", "session": ctx.decision_session, "as_of": ctx.decided_at, "complete": complete, "cash": _ms(cash),
                      "positions": rows, "unresolved_positions": unresolved, "equity": _ms(equity) if complete else None,
                      "return": str(((equity - initial) / initial).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)) if complete and initial else None,
                      "realized_pnl_total": snap["realized_pnl_total"], "refusals": refused + r2,
                      "benchmark": self.benchmark_return(start_session, ctx.decision_session, benchmark, ctx.decided_at, ctx.calendar),
                      "review_only": True, "live_trading_enabled": False, "training_eligible": False, "M4_complete": False}
            if hypothetical_terminal_marks:
                scen_rows, scen_gross, covered = {}, Decimal("0.00"), True
                for symbol, qty in sorted(snap["positions"].items()):
                    hm = [m for m in hypothetical_terminal_marks if m.symbol == symbol]
                    if not hm:
                        covered = False
                        scen_rows[symbol] = {"quantity": qty, "hypothetical_value": None}
                        continue
                    value = _cents(_dec(hm[-1].price, "hypothetical mark") * Decimal(qty))
                    scen_gross += value
                    scen_rows[symbol] = {"quantity": qty, "hypothetical_mark": _ms(_dec(hm[-1].price, "m")), "hypothetical_value": _ms(value), "source_ref": hm[-1].source_ref}
                report["hypothetical_terminal_scenario"] = {"label": "HYPOTHETICAL - not execution evidence; nothing posted to the ledger", "covered": covered,
                                                            "positions": scen_rows, "hypothetical_equity": _ms(cash + scen_gross) if covered else None,
                                                            "ledger_cash_unchanged": _ms(cash)}
            return copy.deepcopy(report)

    # ------------------------------------------------------------------ chain
    def _commit(self, record: dict[str, Any]) -> dict[str, Any]:
        record["review_only"], record["live_trading_enabled"], record["training_eligible"] = True, False, False
        record["state_summary"] = {"intents": {k: v["status"] for k, v in sorted(self._state["intents"].items())}, "reservations": sorted(self._state["reservations"]),
                                   "exit_sessions": dict(sorted(self._state["exit_sessions"].items())), "ledger_state_hash": self.ledger.state_hash}
        body = json.loads(canonical_json(record))
        self._hash = sha256_text(canonical_json({"previous": self._hash, "record": body}))
        body["record_hash"] = self._hash
        self._records.append(body)
        return copy.deepcopy(body)


# ---------------------------------------------------------------------- helpers
def _str(value: Any, what: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise RiskInputError("invalid_input", f"{what} must be a non-empty string, got {value!r}")
    return value


def _int(value: Any, what: str, minimum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise RiskInputError("invalid_input", f"{what} must be an int >= {minimum}, got {value!r}")
    return value


def _dec(value: Any, what: str) -> Decimal:
    if isinstance(value, bool) or isinstance(value, float):
        raise RiskInputError("invalid_input", f"{what} must be Decimal, int or decimal string (not float/bool), got {value!r}")
    try:
        d = Decimal(value) if not isinstance(value, str) else Decimal(value.strip())
    except Exception as exc:  # noqa: BLE001
        raise RiskInputError("invalid_input", f"{what} is not a number: {value!r}") from exc
    if not d.is_finite():
        raise RiskInputError("invalid_input", f"{what} must be finite")
    return d


def _cents(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def _floor_cents(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_FLOOR)


def _ms(value: Decimal) -> str:
    return str(_cents(value))


def _inst(text: str) -> datetime:
    dt = datetime.fromisoformat(text[:-1] + "+00:00" if text.endswith("Z") else text)
    if dt.tzinfo is None:
        raise ValueError(f"naive instant {text}")
    return dt


def _tick(ctx: DecisionContext) -> Decimal:
    return Decimal(format(_dec(ctx.assumptions.tick_size, "tick").normalize(), "f"))


def _round_tick(price: Decimal, tick: Decimal, direction: str) -> Decimal:
    n = (price / tick).to_integral_value(rounding=ROUND_CEILING if direction == "up" else ROUND_FLOOR)
    return (n * tick).quantize(tick)


def _estimate(quantity: int, price: Decimal, ctx: DecisionContext) -> Decimal:
    """Estimated buy cost at ``price``: gross + max(round(gross x buy commission), min) + round(gross x transfer) - the kernel's own charge rules."""
    fees = ctx.fee_schedule
    gross = _cents(price * Decimal(quantity))
    commission = max(_cents(gross * _dec(fees.buy_commission_rate, "c")), _cents(_dec(fees.min_commission, "m")))
    transfer = _cents(gross * _dec(fees.transfer_fee_rate, "t"))
    return gross + commission + transfer


def _affordable(budget: Decimal, price: Decimal, ctx: DecisionContext, *, sizing_cap: int | None) -> tuple[int, Decimal]:
    """Largest lot-conformant quantity whose estimated cost fits the budget (0 when even the minimum lot does not)."""
    lot = ctx.assumptions.lot_policy
    if price <= 0 or budget <= 0:
        return 0, Decimal("0.00")
    q = int((budget / price).to_integral_value(rounding=ROUND_FLOOR)) // lot.buy_increment * lot.buy_increment
    if sizing_cap is not None:
        q = min(q, sizing_cap)
    while q >= lot.min_buy_quantity and _estimate(q, price, ctx) > budget:
        q -= lot.buy_increment
    if q < lot.min_buy_quantity:
        return 0, Decimal("0.00")
    return q, _estimate(q, price, ctx)


def _rec(value: Any) -> Any:
    if hasattr(value, "__dataclass_fields__"):
        return {f: _rec(getattr(value, f)) for f in value.__dataclass_fields__}
    if isinstance(value, (tuple, list)):
        return [_rec(v) for v in value]
    if isinstance(value, Decimal):
        return format(value.normalize(), "f")
    return value


__all__ = ["RISK_CONTRACT_VERSION", "RISK_POLICY", "RISK_POLICY_HASH", "RiskInputError", "Mark", "Signal", "SecurityStatus", "BenchmarkObservation", "RiskPolicy",
           "UniverseMember", "DecisionContext", "AttemptEvidence", "PolicyEngine", "canonical_json", "sha256_text"]
