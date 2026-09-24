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
    "chronology_violation", "phase_mismatch", "context_mismatch", "before_eligible", "invalid_evidence", "kernel_would_reject",
)
PHASES = ("open_auction", "continuous", "close_auction")

_POLICY_SOURCE: dict[str, Any] = {
    "namespace": RISK_NAMESPACE, "contract_version": RISK_CONTRACT_VERSION,
    "kernel": {"module": "backend/app/research/m4_execution.py", "policy_hash": "9bea83482d545e6f39dd8eb70e89d674dd5d900378b596c243da8e122c273e62"},
    "ledger": {"module": "backend/app/research/m4_portfolio.py", "policy_hash": "633f78d987141b0e3dccad5d8e711b241a2eaf58b2a8dbe65e57603b5624d6f6"},
    "evidence_time": "observed_at <= decided_at and available_at <= decided_at for every mark/signal/status/benchmark item consumed by a decision; otherwise refused (future_evidence)",
    "valuation": {"mark": "eligible mark = latest mark of the symbol observed on a session with 0 <= session_age <= max_mark_age_sessions (calendar sessions), available by decided_at; "
                          "mark prices must be positive tick multiples and are re-spelled at the tick scale; benchmark levels are quantized to 0.01",
                  "selection": "one selection rule for decision valuation, execution re-check and performance: candidates are compared as aware instants (never as strings); "
                               "the latest observed_at wins; distinct normalized values at that latest instant are a conflict (inconsistent_evidence, atomic refusal / unresolved "
                               "symbol) - never an input-order pick; equal normalized values are duplicates, not conflicts; ties on identical values are broken by "
                               "(available_at, source_ref) so input order is irrelevant; the selected mark's price, observed_at, available_at, source_ref, session and age are "
                               "bound in the record; the same rule orders security statuses, benchmark levels and hypothetical terminal marks",
                  "missing": "held symbol without eligible mark -> valuation incomplete; position retained and listed; no zero/cost/later-close fallback",
                  "equity": "cash + sum(quantity x mark) over valued positions; gross_exposure = sum(quantity x mark); weight = value / equity"},
    "chronology": "policy-wide event clock = the instant of the last state-changing policy event (a decision's decided_at, an attempt's executed_at once it expired, cancelled, "
                  "downsized or reached the ledger, a cancellation's at); every state-changing path (decide, execute incl. expiry and zero-affordability cancellation, cancel) "
                  "checks its instant against max(event clock, ledger last recorded attempt) BEFORE any state change and refuses earlier instants (chronology_violation) with "
                  "an audit record only - intents, reservations, cooldowns and the ledger are untouched; a performance view must not be earlier than the ledger's last "
                  "recorded attempt; equal instants are allowed and ordered by record sequence; refusals and duplicates never advance the clock; earlier records are never rewritten",
    "intent_binding": "at creation an intent binds its declared execution phase (policy.entry_phase / exit_phase), eligible_from (next session open), expiry session and expires_at, "
                      "the kernel calendar prefix record through the expiry session (sessions, clocks, halts in the prefix, provenance), the fee schedule record and the "
                      "execution assumptions record; every attempt must present the same context (context_mismatch otherwise) and the same phase (phase_mismatch); "
                      "sessions/halts after the expiry session are an unrelated suffix",
    "attempt_validation": "before any state change: evidence dataclasses validated, symbol/session/phase consistency, observed_at/available_at <= executed_at, "
                          "context binding, eligibility; invalid, mismatched or future evidence is an atomic refusal; a valid attempt after expires_at expires the intent "
                          "(reservation released); a decision whose decided_at is after an intent's expires_at also expires it",
    "sizing": {"order": "signals processed in stable (symbol, signal_id) order; each reservation reduces the rooms of the next",
               "rooms": "position_room = max_position_weight x equity - existing value; portfolio_room = max_gross_exposure x equity - gross_exposure - reserved_exposure; "
                        "cash_room = cash - min_cash_reserve - reserved_cash; budget = min(rooms)",
               "quantity": "largest lot multiple q with estimated_cost(q, reserved_price) <= budget where reserved_price = ceil_tick(mark x (1 + slippage_rate)) and "
                           "estimated_cost = q x reserved_price + max(round(gross x buy_commission_rate), min_commission) + round(gross x transfer_fee_rate)",
               "zero": "q < min_buy_quantity -> zero-size decision with reason insufficient_cash_or_room; never a forced minimum lot",
               "limit_price": "buy ceil_tick(mark x (1 + max_gap_pct)); sell floor_tick(mark x (1 - max_gap_pct)); a fill beyond the limit is left unfilled by the kernel",
               "reservation": "budget reserved per intent with original / consumed / remaining; every applied fill debits its actual cost (gross + commission + transfer) from the same "
                              "reservation; released on filled/expired/cancelled; retained (remaining only) while pending/partially_filled/unfilled_live; released or consumed "
                              "amounts are never re-used by another pending intent"},
    "execution_recheck": "at execution the permissible spend is min(remaining reservation, current position room, current portfolio room, current cash room) where the current rooms "
                         "use the ledger's cash now, the target symbol valued at the observed execution print and other holdings at the LATEST causally eligible mark under the "
                         "valuation selection rule with reference session = execution session and window max_mark_age_sessions + 1, available by executed_at (missing/stale -> "
                         "refusal valuation_incomplete; conflicting -> refusal valuation_incomplete with inconsistent_evidence per symbol); the selected marks and the target print "
                         "are bound in recheck.marks / recheck.target; the affordable quantity at the kernel's slipped fill price is then min(remaining quantity, lots that fit): "
                         "downsize (gap_downsized) or cancel (gap_exceeds_budget); never enlarge; never a later close",
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
    entry_phase: str = "open_auction"
    exit_phase: str = "open_auction"

    def validated(self) -> "RiskPolicy":
        for name in ("entry_phase", "exit_phase"):
            if getattr(self, name) not in PHASES:
                raise RiskInputError("invalid_policy", f"{name} must be one of {PHASES}")
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
                                       "decisions": 0, "attempts": 0, "event_clock": None}
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
            remaining = sum((Decimal(r["remaining"]) for r in st["reservations"].values()), Decimal("0.00"))
            return {"by_intent": copy.deepcopy(st["reservations"]), "reserved_cash": _ms(remaining), "reserved_exposure": _ms(remaining),
                    "consumed_total": _ms(sum((Decimal(r["consumed"]) for r in st["reservations"].values()), Decimal("0.00")))}

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

    @staticmethod
    def _latest(rows: list) -> tuple[Any, str, list[str]]:
        """Shared selection rule.  ``rows`` are (observed instant, available instant, source_ref, normalized value, item).
        Returns (item at the latest observed instant, that instant, distinct normalized values at it).  Ordering uses aware
        instants, then provenance and value, so the input order is irrelevant; more than one value at the latest instant
        is a conflict for the caller to refuse."""
        rows = sorted(rows, key=lambda x: (x[0], x[1], x[2], x[3]))
        latest = rows[-1][0]
        return rows[-1][4], latest.isoformat(), sorted({x[3] for x in rows if x[0] == latest})

    def _select_mark(self, symbol: str, marks: list, ctx: DecisionContext, index: dict[str, int], ref_session: str, max_age: int) -> tuple[Mark | None, dict[str, Any] | None, dict[str, Any] | None]:
        """Latest eligible mark of ``symbol`` relative to ``ref_session`` within ``max_age`` sessions; returns (mark, refusal, bound evidence).
        Prices must be positive tick multiples and are re-spelled at the tick scale (equivalent spellings are one value);
        conflicting values at the latest observed instant are refused, never picked by input order."""
        rows = []
        tick = _tick(ctx)
        for m in marks:
            if m.symbol != symbol:
                continue
            price = _dec(m.price, "mark price")
            if price <= 0 or (price / tick) != (price / tick).to_integral_value():
                return None, {"code": "inconsistent_evidence", "symbol": symbol, "detail": f"mark price {price} is not a positive multiple of tick {tick}"}, None
            m = replace(m, price=price.quantize(tick))
            observed, available = _inst(m.observed_at), _inst(m.available_at)
            session = ctx.calendar.local_date(observed)
            if session not in index or index[ref_session] - index[session] < 0:
                continue
            rows.append((observed, available, m.source_ref, str(m.price), (m, session, index[ref_session] - index[session])))
        if not rows:
            return None, {"code": "missing_mark", "symbol": symbol}, None
        (mark, session, age), latest_at, values = self._latest(rows)
        if len(values) > 1:
            return None, {"code": "inconsistent_evidence", "symbol": symbol, "detail": f"conflicting marks at {latest_at}: {values}", "observed_at": latest_at, "conflicting_prices": values}, None
        if age > max_age:
            return None, {"code": "stale_mark", "symbol": symbol, "age_sessions": age, "max_age": max_age, "observed_at": mark.observed_at}, None
        bound = {"price": str(mark.price), "observed_at": mark.observed_at, "available_at": mark.available_at, "source_ref": mark.source_ref, "session": session, "age_sessions": age}
        return mark, None, bound

    def _mark_for(self, symbol: str, marks: list, ctx: DecisionContext, index: dict[str, int]) -> tuple[Mark | None, dict[str, Any] | None, dict[str, Any] | None]:
        return self._select_mark(symbol, marks, ctx, index, ctx.decision_session, self.policy.max_mark_age_sessions)

    def _status_at(self, symbol: str, statuses: list) -> tuple[str | None, dict[str, Any] | None]:
        """Latest security status by aware instants; conflicting statuses at the latest instant are inconsistent evidence."""
        rows = [(_inst(s.observed_at), _inst(s.available_at), s.source_ref, s.status, s) for s in statuses if s.symbol == symbol]
        if not rows:
            return "listed", None
        item, latest_at, values = self._latest(rows)
        if len(values) > 1:
            return None, {"code": "inconsistent_evidence", "symbol": symbol, "detail": f"conflicting security statuses at {latest_at}: {values}", "observed_at": latest_at, "conflicting_statuses": values}
        return item.status, None

    def _chronology_floor(self, work: dict[str, Any]) -> tuple[datetime | None, str | None, str | None]:
        """(floor instant, ledger last recorded attempt, policy event clock): no state-changing event may precede the floor."""
        ledger_last = self.ledger.snapshot()["last_executed_at"]
        clock = work["event_clock"]
        instants = [_inst(v) for v in (ledger_last, clock) if v is not None]
        return (max(instants) if instants else None), ledger_last, clock

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
                floor, ledger_last, clock = self._chronology_floor(work)
                if floor is not None and decided_at < floor:
                    raise _Refuse("chronology_violation", f"decided_at {ctx.decided_at} precedes the ledger's last recorded attempt ({ledger_last}) or the policy event clock ({clock}); "
                                  "that state is from the future of this decision", ledger_last_executed_at=ledger_last, policy_event_clock=clock)
                if work["last_decided_at"] is not None and decided_at < _inst(work["last_decided_at"]):     # subsumed by the event clock; kept as an invariant
                    raise _Refuse("chronology_violation", f"decided_at {ctx.decided_at} precedes the previous decision {work['last_decided_at']}", policy_event_clock=clock)
                if decision_id in {r["decision_id"] for r in self._records if r["kind"] == "decision"}:
                    raise _Refuse("duplicate_signal", f"decision_id {decision_id} already recorded")
                # ---- deterministic expiry sweep: intents whose bound expiry instant is already past
                expired_now = []
                for iid, it in sorted(work["intents"].items()):
                    if it["status"] in ("pending", "partially_filled", "unfilled_live") and decided_at > _inst(it["expires_at"]):
                        it["status"] = "expired"
                        released = work["reservations"].pop(iid, None)
                        expired_now.append({"intent_id": iid, "expires_at": it["expires_at"], "released_remaining": released["remaining"] if released else None})
                record["expired_intents"] = expired_now
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
                    mark, refusal, mark_ev = self._mark_for(symbol, ok_marks, ctx, index)
                    status, status_refusal = self._status_at(symbol, ok_status)
                    lots = snap["lots"][symbol]
                    cost_remaining = sum((Decimal(l["cost_remaining"]) for l in lots if l["quantity_remaining"] > 0), Decimal("0.00"))
                    entry_ref = (cost_remaining / Decimal(qty)) if qty else None
                    entry_session = min(l["acquired_session"] for l in lots if l["quantity_remaining"] > 0)
                    row = {"quantity": qty, "status": status, "entry_cost_reference": str(entry_ref.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)) if entry_ref is not None else None,
                           "entry_session": entry_session, "sessions_held": index[ctx.decision_session] - index[entry_session] if entry_session in index else None}
                    if status_refusal is not None or mark is None or status == "delisted":
                        row.update({"mark": None, "value": None, "weight": None, "unresolved_reason": status_refusal or refusal or {"code": "security_not_tradable", "status": status}})
                        incomplete.append(symbol)
                    else:
                        price = _dec(mark.price, "mark price")
                        value = _cents(price * Decimal(qty))
                        gross += value
                        row.update({"mark": str(price), "mark_observed_at": mark.observed_at, "mark_available_at": mark.available_at, "mark_source_ref": mark.source_ref,
                                    "mark_age_sessions": mark_ev["age_sessions"], "value": _ms(value), "weight": None})
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
                reserved_cash = sum((Decimal(r["remaining"]) for r in work["reservations"].values()), Decimal("0.00"))
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
                        status, status_refusal = self._status_at(sig.symbol, ok_status)
                        if status_refusal is not None:
                            raise _Refuse("inconsistent_evidence", canonical_json(status_refusal))
                        if status != "listed":
                            raise _Refuse("security_not_tradable", f"status {status}", status=status)
                        mark, refusal, mark_ev = self._mark_for(sig.symbol, ok_marks, ctx, index)
                        if mark is None:
                            raise _Refuse(refusal["code"], canonical_json(refusal))
                        price = _dec(mark.price, "mark price")
                        position_room = _dec(self.policy.max_position_weight, "w") * equity
                        portfolio_room = _dec(self.policy.max_gross_exposure, "g") * equity - gross - reserved_exposure
                        cash_room = cash - _dec(self.policy.min_cash_reserve, "reserve") - reserved_cash
                        budget = _floor_cents(min(position_room, portfolio_room, cash_room))
                        reserved_price = _round_tick(price * (Decimal(1) + _dec(ctx.assumptions.slippage_rate, "slip")), _tick(ctx), "up")
                        quantity, estimate = _affordable(budget, reserved_price, ctx, sizing_cap=None)
                        rooms = {"position_room": _ms(_floor_cents(position_room)), "portfolio_room": _ms(_floor_cents(portfolio_room)), "cash_room": _ms(_floor_cents(cash_room)), "budget": _ms(budget),
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
                                        "estimated_cost": _ms(estimate), "reserved_budget": _ms(budget), "mark_evidence": mark_ev})
                    except _Refuse as exc:
                        entries.append({**entry, "decision": "refused", "reason": exc.code, "detail": exc.detail, **exc.extra})
                record["entries"] = entries
                # ---- benchmark alignment (evidence-time checked; missing is not zero)
                record["benchmark"] = self._benchmark_level(ok_bench, ctx, index)
                work["last_decided_at"] = ctx.decided_at
                work["event_clock"] = ctx.decided_at
                work["decisions"] += 1
                record["reservations_after"] = {"reserved_cash": _ms(reserved_cash), "reserved_exposure": _ms(reserved_exposure)}
                record["status"] = "decided"
                self._state = work
            except _Refuse as exc:
                record["status"] = "refused"
                record["refusals"].append({"code": exc.code, "detail": exc.detail, **exc.extra})
            return self._commit(record)

    def _benchmark_level(self, observations: list, ctx: DecisionContext, index: dict[str, int]) -> dict[str, Any]:
        rows = [(_inst(b.observed_at), _inst(b.available_at), b.source_ref, _ms(_dec(b.level, "level")), b) for b in observations
                if b.symbol == self.benchmark_symbol and ctx.calendar.local_date(_inst(b.observed_at)) == ctx.decision_session]
        if not rows:
            return {"symbol": self.benchmark_symbol, "session": ctx.decision_session, "status": "missing", "level": None}
        b, latest_at, values = self._latest(rows)
        if len(values) > 1:
            return {"symbol": self.benchmark_symbol, "session": ctx.decision_session, "status": "inconsistent_evidence", "level": None, "observed_at": latest_at, "conflicting_levels": values}
        return {"symbol": self.benchmark_symbol, "session": ctx.decision_session, "status": "observed", "level": _ms(_dec(b.level, "level")), "observed_at": b.observed_at,
                "available_at": b.available_at, "source_ref": b.source_ref}

    def _new_intent(self, work, decision_id, ctx, symbol, side, quantity, limit, reason, index, *, mark_ref, mark_at, budget=None, estimated_cost=None) -> dict[str, Any]:
        next_session = ctx.calendar.sessions[index[ctx.decision_session] + 1] if index[ctx.decision_session] + 1 < len(ctx.calendar.sessions) else None
        if next_session is None:
            raise _Refuse("inconsistent_evidence", "no session after the decision session in the injected calendar")
        intent_id = f"{decision_id}:{side}:{symbol}"
        if intent_id in work["intents"]:
            raise _Refuse("duplicate_signal", f"intent {intent_id} already exists")
        expiry_idx = index[next_session] + self.policy.intent_expiry_sessions - 1
        if expiry_idx >= len(ctx.calendar.sessions):
            raise _Refuse("inconsistent_evidence", "intent expiry lies beyond the injected calendar")
        expiry_session = ctx.calendar.sessions[expiry_idx]
        phase = self.policy.entry_phase if side == "buy" else self.policy.exit_phase
        context = {"phase": phase, "eligible_session": next_session, "expiry_session": expiry_session, "expires_at": ctx.calendar.close_at(expiry_session).isoformat(),
                   "calendar_prefix": ctx.calendar.prefix_record(expiry_session), "calendar_clock": {"tz_offset": ctx.calendar.tz_offset, "open_time": ctx.calendar.open_time,
                   "close_time": ctx.calendar.close_time}, "fee_schedule": _rec(ctx.fee_schedule), "assumptions": _rec(ctx.assumptions)}
        intent = {"intent_id": intent_id, "decision_id": decision_id, "symbol": symbol, "side": side, "quantity": quantity, "remaining": quantity, "filled": 0,
                  "limit_price": str(limit), "reason": reason, "status": "pending", "decision_session": ctx.decision_session, "decided_at": ctx.decided_at,
                  "eligible_from": ctx.calendar.open_at(next_session).isoformat(), "eligible_session": next_session, "expiry_sessions": self.policy.intent_expiry_sessions,
                  "expiry_session": expiry_session, "expires_at": context["expires_at"], "phase": phase, "context": context,
                  "context_hash": sha256_text(canonical_json(context)), "mark_source_ref": mark_ref, "mark_observed_at": mark_at, "attempts": [],
                  "budget": _ms(budget) if budget is not None else None, "estimated_cost": _ms(estimated_cost) if estimated_cost is not None else None}
        work["intents"][intent_id] = intent
        if budget is not None:
            work["reservations"][intent_id] = {"symbol": symbol, "original_budget": _ms(budget), "consumed": "0.00", "remaining": _ms(budget), "kind": "buy_cash_and_exposure"}
        return intent

    # ------------------------------------------------------------------ execute
    def execute(self, intent_id: str, ctx: DecisionContext, evidence: AttemptEvidence, *, marks: tuple = ()) -> dict[str, Any]:
        """Attempt one intent through the frozen kernel/ledger.  All evidence, context and eligibility checks run before any
        state change; only a valid attempt can expire, downsize, cancel or fill an intent.  ``marks`` are causally eligible
        valuation marks for other holdings, needed for the current-risk re-check of buys."""
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
                # ---- 1. structural validation of every consumed input (kernel dataclass rules), before anything else
                if not isinstance(evidence, AttemptEvidence):
                    raise _Refuse("invalid_evidence", "evidence must be AttemptEvidence")
                try:
                    _str(evidence.attempt_id, "attempt_id")
                    ctx.calendar.validated(); ctx.fee_schedule.validated(); ctx.assumptions.validated()
                    evidence.tradability.validated(); evidence.price.validated()
                    if evidence.capacity is not None:
                        evidence.capacity.validated()
                    executed_at = _inst(evidence.executed_at)
                except _Refuse:
                    raise
                except Exception as exc:  # noqa: BLE001 - kernel input errors become refusals
                    raise _Refuse("invalid_evidence", f"attempt evidence failed validation: {exc}") from exc
                if any(a["attempt_id"] == evidence.attempt_id for a in intent["attempts"]):
                    record.update({"status": "duplicate", "detail": f"attempt {evidence.attempt_id} already recorded for {intent_id}; no ledger call, no holding/cooldown/reservation change"})
                    return self._commit(record)
                # ---- 1b. policy-wide chronology: no state-changing attempt (fill, expiry, downsize, cancellation) may precede the
                #          ledger's last recorded attempt or the policy event clock; refusal only, nothing released or expired
                floor, ledger_last, clock = self._chronology_floor(work)
                if floor is not None and executed_at < floor:
                    raise _Refuse("chronology_violation", f"executed_at {evidence.executed_at} precedes the ledger's last recorded attempt ({ledger_last}) or the policy event clock ({clock}); "
                                  "the state this attempt would consume is from its future; no cancellation, expiry or release", ledger_last_executed_at=ledger_last, policy_event_clock=clock)
                symbol = intent["symbol"]
                for label, item in (("tradability", evidence.tradability), ("price", evidence.price), ("capacity", evidence.capacity)):
                    if item is not None and item.symbol != symbol:
                        raise _Refuse("invalid_evidence", f"{label} evidence is for {item.symbol}, intent is for {symbol}")
                if evidence.phase not in PHASES or evidence.phase != intent["phase"]:
                    raise _Refuse("phase_mismatch", f"attempt phase {evidence.phase!r} != the intent's declared phase {intent['phase']!r}")
                index = ctx.calendar.index()
                exec_session = ctx.calendar.local_date(executed_at)
                if exec_session not in index or evidence.session != exec_session or evidence.tradability.session != exec_session:
                    raise _Refuse("invalid_evidence", f"attempt session {evidence.session} / tradability session {evidence.tradability.session} != session of executed_at ({exec_session})")
                for label, item in (("tradability", evidence.tradability), ("price", evidence.price), ("capacity", evidence.capacity)):
                    if item is None:
                        continue
                    if _inst(item.observed_at) > executed_at or _inst(item.available_at) > executed_at:
                        raise _Refuse("future_evidence", f"{label} evidence observed {item.observed_at} / available {item.available_at} after executed_at {evidence.executed_at}")
                    if label != "tradability" and ctx.calendar.local_date(_inst(item.observed_at)) != exec_session:
                        raise _Refuse("invalid_evidence", f"{label} evidence observed on another session than the attempt")
                # ---- 2. bound decision context (calendar prefix through the expiry session, clocks, fee/assumption semantics)
                bound = intent["context"]
                try:
                    prefix_now = ctx.calendar.prefix_record(bound["expiry_session"])
                except (KeyError, IndexError):
                    prefix_now = {"prefix_fingerprint": None, "missing": bound["expiry_session"]}
                now = {"calendar_prefix": prefix_now, "calendar_clock": {"tz_offset": ctx.calendar.tz_offset, "open_time": ctx.calendar.open_time, "close_time": ctx.calendar.close_time},
                       "fee_schedule": _rec(ctx.fee_schedule), "assumptions": _rec(ctx.assumptions)}
                changed = sorted(key for key in now if now[key] != bound[key])
                if changed:
                    raise _Refuse("context_mismatch", f"execution context differs from the context bound at intent creation: {changed}", changed=changed, context_hash=intent["context_hash"])
                # ---- 3. eligibility and expiry from the bound temporal contract
                if executed_at < _inst(intent["eligible_from"]):
                    raise _Refuse("before_eligible", f"executed_at {evidence.executed_at} precedes eligible_from {intent['eligible_from']}")
                if executed_at > _inst(intent["expires_at"]):
                    intent["status"] = "expired"
                    released = work["reservations"].pop(intent_id, None)
                    intent["attempts"].append({"attempt_id": evidence.attempt_id, "executed_at": evidence.executed_at, "outcome": "expired_at_attempt",
                                               "expires_at": intent["expires_at"], "released_remaining": released["remaining"] if released else None})
                    work["attempts"] += 1
                    work["event_clock"] = evidence.executed_at
                    record.update({"status": "expired", "expires_at": intent["expires_at"], "released_remaining": released["remaining"] if released else None,
                                   "detail": "valid attempt after the bound expiry: intent expired deterministically; no fill, no fabricated state"})
                    self._state = work
                    return self._commit(record)
                # ---- 4. buys: cumulative budget + current risk re-check at the observed execution print (never a later close)
                quantity = intent["remaining"]
                gap_note = None
                recheck = None
                if intent["side"] == "buy":
                    observed = _dec(evidence.price.price, "execution price").quantize(_tick(ctx))
                    fill_price = _round_tick(observed * (Decimal(1) + _dec(ctx.assumptions.slippage_rate, "slip")), _tick(ctx), "up")
                    reservation = work["reservations"][intent_id]
                    remaining_budget = Decimal(reservation["remaining"])
                    snap = self.ledger.snapshot()
                    cash_now = Decimal(snap["cash"])
                    others_reserved = sum((Decimal(r["remaining"]) for iid, r in work["reservations"].items() if iid != intent_id), Decimal("0.00"))
                    gross_now, target_value, incomplete, mark_evidence, unresolved = Decimal("0.00"), Decimal("0.00"), [], {}, {}
                    ok_marks, refused_marks = self._eligible(list(marks), executed_at, "mark")
                    target = {"symbol": symbol, "valued_at": "observed execution print", "observed_price": str(observed), "price_field": evidence.price.field,
                              "price_observed_at": evidence.price.observed_at, "price_available_at": evidence.price.available_at, "price_source_ref": evidence.price.source_ref}
                    for held, qty in sorted(snap["positions"].items()):
                        if held == symbol:
                            target_value = _cents(observed * Decimal(qty))
                            gross_now += target_value
                            target["held_quantity"] = qty
                            continue
                        mk, refusal, mark_ev = self._select_mark(held, ok_marks, ctx, index, exec_session, self.policy.max_mark_age_sessions + 1)
                        if mk is None:
                            incomplete.append(held)
                            unresolved[held] = refusal
                            continue
                        mark_evidence[held] = {**mark_ev, "quantity": qty, "value": _ms(_cents(_dec(mk.price, "mark") * Decimal(qty)))}
                        gross_now += _cents(_dec(mk.price, "mark") * Decimal(qty))
                    if incomplete:
                        raise _Refuse("valuation_incomplete", f"current-risk re-check needs one latest causally eligible mark per held symbol; unresolved {incomplete}",
                                      symbols=incomplete, unresolved=unresolved, refused_marks=refused_marks)
                    equity_now = cash_now + gross_now
                    position_room = _dec(self.policy.max_position_weight, "w") * equity_now - target_value
                    portfolio_room = _dec(self.policy.max_gross_exposure, "g") * equity_now - gross_now - others_reserved
                    cash_room = cash_now - _dec(self.policy.min_cash_reserve, "reserve") - others_reserved
                    permissible = _floor_cents(min(remaining_budget, position_room, portfolio_room, cash_room))
                    affordable, estimate = _affordable(permissible, fill_price, ctx, sizing_cap=quantity)
                    recheck = {"observed_price": str(observed), "fill_price_estimate": str(fill_price), "reservation_original": reservation["original_budget"],
                               "reservation_consumed": reservation["consumed"], "reservation_remaining": _ms(remaining_budget), "cash_now": _ms(cash_now),
                               "equity_now": _ms(equity_now), "gross_now": _ms(gross_now), "position_room": _ms(_floor_cents(position_room)), "portfolio_room": _ms(_floor_cents(portfolio_room)),
                               "cash_room": _ms(_floor_cents(cash_room)), "permissible": _ms(permissible), "affordable_quantity": affordable, "estimated_cost": _ms(estimate),
                               "target": target, "marks": mark_evidence, "refused_marks": refused_marks}
                    if affordable <= 0:
                        # confirm the evidence is executable at all (dry run, no state) before cancelling on affordability
                        probe = self._request(intent, ctx, evidence, ctx.assumptions.lot_policy.min_buy_quantity)
                        dry = self.kernel.execute(probe)
                        affordability_only = all(r["code"] == "insufficient_cash" for r in dry.record["reasons"])
                        if dry.record["status"] == "rejected" and not affordability_only:
                            raise _Refuse("kernel_would_reject", "the frozen kernel rejects this attempt evidence; no cancellation on invalid evidence",
                                          kernel_reasons=dry.record["reasons"], recheck=recheck)
                        intent["status"] = "cancelled"
                        released = work["reservations"].pop(intent_id, None)
                        intent["attempts"].append({"attempt_id": evidence.attempt_id, "executed_at": evidence.executed_at, "outcome": "cancelled_gap_exceeds_budget", "recheck": recheck})
                        work["attempts"] += 1
                        work["event_clock"] = evidence.executed_at
                        record.update({"status": "cancelled", "reason": "gap_exceeds_budget", "recheck": recheck, "released_remaining": released["remaining"] if released else None})
                        self._state = work
                        return self._commit(record)
                    if affordable < quantity:
                        gap_note = {"code": "gap_downsized", "from": quantity, "to": affordable, "recheck": recheck}
                        quantity = affordable
                # ---- 5. apply through the frozen kernel and ledger (atomic there); then debit the reservation with the actual cost
                req = self._request(intent, ctx, evidence, quantity)
                work["sequence"] += 1
                event = self.lm.AttemptEvent(f"{intent_id}:{evidence.attempt_id}", work["sequence"], req)
                ledger_record = self.ledger.apply(event)
                kstatus = (ledger_record.get("kernel") or {}).get("status")
                outcome = {"attempt_id": evidence.attempt_id, "executed_at": evidence.executed_at, "ledger_status": ledger_record["status"], "kernel_status": kstatus,
                           "committed": ledger_record["committed"], "quantity_attempted": quantity, "gap": gap_note, "recheck": recheck,
                           "ledger_event_record_hash": ledger_record["event_record_hash"], "reasons": ledger_record["reasons"]}
                if ledger_record["status"] == "applied":
                    filled = ledger_record["effects"]["filled_quantity"]
                    intent["filled"] += filled
                    intent["remaining"] = quantity - filled
                    if gap_note is not None:
                        intent["quantity"] = intent["filled"] + intent["remaining"]
                    outcome.update({"filled_quantity": filled, "fill_price": ledger_record["effects"]["fill_price"], "fees": ledger_record["effects"]["fees"],
                                    "cash_after": ledger_record["effects"]["cash_after"]})
                    live = ledger_record["order"]["live"]
                    if intent["side"] == "buy":
                        reservation = work["reservations"][intent_id]
                        cost = -Decimal(ledger_record["effects"]["cash_delta"])
                        reservation["consumed"] = _ms(Decimal(reservation["consumed"]) + cost)
                        reservation["remaining"] = _ms(Decimal(reservation["original_budget"]) - Decimal(reservation["consumed"]))
                        if Decimal(reservation["remaining"]) < 0:
                            raise _Refuse("inconsistent_evidence", "applied cost exceeds the reservation; internal invariant")
                        outcome["reservation"] = dict(reservation)
                        work["entry_sessions"][symbol] = ledger_record["effects"]["lot_created"]["acquired_session"]
                    if intent["remaining"] == 0:
                        intent["status"] = "filled"
                        work["reservations"].pop(intent_id, None)
                    else:
                        intent["status"] = "partially_filled" if live else "expired"
                        if not live:
                            work["reservations"].pop(intent_id, None)
                    if intent["side"] == "sell" and self.ledger.positions().get(symbol, 0) == 0:
                        work["exit_sessions"][symbol] = ledger_record["effects"]["sale"]["session"]     # cooldown starts on the actual full exit
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
                work["event_clock"] = evidence.executed_at
                record.update({"status": intent["status"], "outcome": outcome, "ledger_record": ledger_record})
                self._state = work
            except _Refuse as exc:
                record.update({"status": "refused", "reason": exc.code, "detail": exc.detail, **exc.extra})
            return self._commit(record)

    def _request(self, intent: dict[str, Any], ctx: DecisionContext, evidence: AttemptEvidence, quantity: int) -> Any:
        """Kernel request for an intent attempt: the order terms come from the intent's bound context, never from the evidence."""
        k = self.kernel
        member = self.universe[intent["symbol"]]
        return k.ExecutionRequest(
            decision=k.Decision(intent["decision_id"] + ":" + intent["symbol"], intent["symbol"], intent["side"], intent["decision_session"], intent["decided_at"],
                                (k.InputAvailability("valuation_mark", intent["mark_observed_at"], intent["mark_source_ref"]),), f"{self.policy.policy_id}:{intent['reason']}"),
            order=k.Order(intent["intent_id"], intent["decision_id"] + ":" + intent["symbol"], intent["symbol"], intent["side"], quantity, intent["limit_price"], intent["decided_at"],
                          intent["eligible_from"], intent["expiry_sessions"], intent["phase"]),
            instrument=k.Instrument(member.symbol, "stock", member.board, member.listing_evidence_ref, ctx.calendar.source_ref, True),
            calendar=ctx.calendar, tradability=evidence.tradability, price=evidence.price,
            account=self.ledger.account_state(evidence.executed_at, intent["symbol"]), fee_schedule=ctx.fee_schedule, assumptions=ctx.assumptions,
            attempt=k.ExecutionAttempt(evidence.attempt_id, evidence.executed_at, evidence.session, evidence.phase), capacity=evidence.capacity)

    def cancel(self, intent_id: str, reason: str, *, at: str | None = None) -> dict[str, Any]:
        """Explicit cancellation.  ``at`` (aware instant) is checked against the policy-wide chronology like any other
        state-changing event and advances the event clock; without ``at`` the cancellation is stamped at the current
        event clock (it can never be placed earlier than the state it changes)."""
        with localcontext(self.kernel.ARITHMETIC_CONTEXT):
            work = copy.deepcopy(self._state)
            record = {"schema": f"{RISK_NAMESPACE}.cancel.v1", "engine_id": self.engine_id, "kind": "cancel", "intent_id": intent_id, "reason": reason, "at": at, "chain_hash_before": self._hash}
            intent = work["intents"].get(intent_id)
            if intent is None or intent["status"] not in ("pending", "partially_filled", "unfilled_live"):
                record["status"] = "refused"
                record["detail"] = "unknown intent or not cancellable"
                return self._commit(record)
            floor, ledger_last, clock = self._chronology_floor(work)
            if at is not None:
                try:
                    at_inst = _inst(at)
                except (ValueError, TypeError) as exc:
                    record.update({"status": "refused", "reason_code": "invalid_evidence", "detail": f"cancellation instant invalid: {exc}"})
                    return self._commit(record)
                if floor is not None and at_inst < floor:
                    record.update({"status": "refused", "reason_code": "chronology_violation", "ledger_last_executed_at": ledger_last, "policy_event_clock": clock,
                                   "detail": f"cancellation at {at} precedes the ledger's last recorded attempt ({ledger_last}) or the policy event clock ({clock}); nothing released"})
                    return self._commit(record)
                work["event_clock"] = at
            else:
                record["at"] = clock
            intent["status"] = "cancelled"
            released = work["reservations"].pop(intent_id, None)
            record["status"] = "cancelled"
            record["released_reservation"] = intent.get("budget")
            record["released_remaining"] = released["remaining"] if released else None
            self._state = work
            return self._commit(record)

    # ------------------------------------------------------------------ benchmark and performance
    def benchmark_return(self, start_session: str, end_session: str, observations: tuple, as_of: str, calendar: Any) -> dict[str, Any]:
        with localcontext(self.kernel.ARITHMETIC_CONTEXT):
            at = _inst(as_of)
            ok, refused = self._eligible(list(observations), at, "benchmark")
            index = calendar.index()
            out = {"symbol": self.benchmark_symbol, "start_session": start_session, "end_session": end_session, "as_of": as_of, "refusals": refused}
            levels, conflicts = {}, {}
            for session in (start_session, end_session):
                rows = [(_inst(b.observed_at), _inst(b.available_at), b.source_ref, _ms(_dec(b.level, "level")), b) for b in ok
                        if b.symbol == self.benchmark_symbol and calendar.local_date(_inst(b.observed_at)) == session]
                levels[session] = None
                if rows:
                    b, latest_at, values = self._latest(rows)
                    if len(values) > 1:
                        conflicts[session] = {"observed_at": latest_at, "conflicting_levels": values}
                    else:
                        levels[session] = _ms(_dec(b.level, "level"))
            out["levels"] = levels
            if conflicts:
                out.update({"status": "inconsistent_evidence", "return": None, "conflicts": conflicts, "note": "conflicting benchmark levels at the latest instant are refused, never picked by input order"})
            elif start_session not in index or end_session not in index or index[end_session] < index[start_session]:
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
            snap = self.ledger.snapshot()
            if snap["last_executed_at"] is not None and decided_at < _inst(snap["last_executed_at"]):
                return {"schema": f"{RISK_NAMESPACE}.performance.v1", "session": ctx.decision_session, "as_of": ctx.decided_at, "status": "refused", "reason": "chronology_violation",
                        "detail": f"as_of {ctx.decided_at} precedes the ledger's last recorded attempt {snap['last_executed_at']}; no view of earlier holdings from later state",
                        "complete": False, "equity": None, "return": None, "review_only": True, "live_trading_enabled": False, "training_eligible": False, "M4_complete": False}
            ok_marks, refused = self._eligible(list(marks), decided_at, "mark")
            ok_status, r2 = self._eligible(list(statuses), decided_at, "status")
            index = ctx.calendar.index()
            cash = Decimal(snap["cash"])
            rows, unresolved, gross = {}, [], Decimal("0.00")
            for symbol, qty in sorted(snap["positions"].items()):
                mark, refusal, mark_ev = self._mark_for(symbol, ok_marks, ctx, index)
                status, status_refusal = self._status_at(symbol, ok_status)
                if status_refusal is not None or mark is None or status == "delisted":
                    reason = status_refusal or refusal or {"code": "security_not_tradable", "status": status}
                    limitation = ("frozen contracts carry no verified executable exit, settlement or corporate-action support for a delisted holding; "
                                  "the position is retained unresolved and no liquidation cash is posted") if status == "delisted" else "no eligible mark at this session"
                    rows[symbol] = {"quantity": qty, "status": status, "value": None, "unresolved_reason": reason, "limitation": limitation}
                    unresolved.append(symbol)
                else:
                    value = _cents(_dec(mark.price, "mark") * Decimal(qty))
                    gross += value
                    rows[symbol] = {"quantity": qty, "status": status, "mark": str(mark.price), "value": _ms(value), "mark_evidence": mark_ev}
            complete = not unresolved
            initial = _cents(_dec(initial_cash, "initial_cash"))
            equity = cash + gross if complete else None
            report = {"schema": f"{RISK_NAMESPACE}.performance.v1", "session": ctx.decision_session, "as_of": ctx.decided_at, "complete": complete, "cash": _ms(cash),
                      "positions": rows, "unresolved_positions": unresolved, "equity": _ms(equity) if complete else None,
                      "return": str(((equity - initial) / initial).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)) if complete and initial else None,
                      "realized_pnl_total": snap["realized_pnl_total"], "refusals": refused + r2, "status": "valued" if complete else "incomplete",
                      "benchmark": self.benchmark_return(start_session, ctx.decision_session, benchmark, ctx.decided_at, ctx.calendar),
                      "review_only": True, "live_trading_enabled": False, "training_eligible": False, "M4_complete": False}
            if hypothetical_terminal_marks:
                scen_rows, scen_gross, covered = {}, Decimal("0.00"), True
                for symbol, qty in sorted(snap["positions"].items()):
                    try:
                        hm = [(_inst(m.observed_at), _inst(m.available_at), m.source_ref, _ms(_dec(m.price, "hypothetical mark")), m) for m in hypothetical_terminal_marks if m.symbol == symbol]
                    except (ValueError, TypeError, RiskInputError) as exc:
                        covered = False
                        scen_rows[symbol] = {"quantity": qty, "hypothetical_value": None, "unresolved_reason": {"code": "inconsistent_evidence", "detail": f"hypothetical mark invalid: {exc}"}}
                        continue
                    if not hm:
                        covered = False
                        scen_rows[symbol] = {"quantity": qty, "hypothetical_value": None}
                        continue
                    chosen, latest_at, values = self._latest(hm)
                    if len(values) > 1:
                        covered = False
                        scen_rows[symbol] = {"quantity": qty, "hypothetical_value": None, "unresolved_reason": {"code": "inconsistent_evidence", "observed_at": latest_at, "conflicting_prices": values}}
                        continue
                    value = _cents(_dec(chosen.price, "hypothetical mark") * Decimal(qty))
                    scen_gross += value
                    scen_rows[symbol] = {"quantity": qty, "hypothetical_mark": _ms(_dec(chosen.price, "m")), "hypothetical_value": _ms(value), "source_ref": chosen.source_ref,
                                         "observed_at": chosen.observed_at}
                report["hypothetical_terminal_scenario"] = {"label": "HYPOTHETICAL - not execution evidence; nothing posted to the ledger", "covered": covered,
                                                            "positions": scen_rows, "hypothetical_equity": _ms(cash + scen_gross) if covered else None,
                                                            "ledger_cash_unchanged": _ms(cash)}
            return copy.deepcopy(report)

    # ------------------------------------------------------------------ chain
    def _commit(self, record: dict[str, Any]) -> dict[str, Any]:
        record["review_only"], record["live_trading_enabled"], record["training_eligible"] = True, False, False
        record["state_summary"] = {"intents": {k: v["status"] for k, v in sorted(self._state["intents"].items())}, "reservations": sorted(self._state["reservations"]),
                                   "exit_sessions": dict(sorted(self._state["exit_sessions"].items())), "event_clock": self._state["event_clock"], "ledger_state_hash": self.ledger.state_hash}
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
