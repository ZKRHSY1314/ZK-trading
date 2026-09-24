"""M4-02A synthetic, in-memory, deterministic portfolio / FIFO cash ledger over the frozen M4-01 kernel.

The ledger consumes explicitly ordered ``AttemptEvent`` objects, each carrying an already-sized
``ExecutionRequest`` of the frozen execution kernel (``backend/app/research/m4_execution.py``,
integration revision ``M4-01-codex-integration-1``).  The kernel module is **injected** (``PortfolioLedger(
kernel=...)``); this file never imports ``app``, settings, a database, the filesystem, the network or a
clock.  Standard library only.

What it keeps: cash, per-symbol FIFO inventory lots with acquired session, remaining cost basis and
provenance (event / order / attempt / kernel result identities), per-order cumulative fills, per-capacity
consumption budgets (shares or CNY), realized PnL, and a hash chain of event records and states.

What it guarantees (each item is a test in ``backend/tests/test_m4_portfolio.py``):

* The ``AccountState`` handed to the kernel is derived from the ledger **for the requested symbol only**
  (shared cash, that symbol's FIFO lots - the kernel's inventory is symbol-less, so the ledger adapts it);
  an externally supplied state that does not match (content or ``as_of``) is rejected before any execution.
* Only ``filled`` / ``partially_filled`` kernel results change cash or lots; rejected and unfilled results
  are recorded with their kernel reasons and zero effect.  There is no public method that applies a cash
  or quantity delta without a kernel result that the ledger itself produced and re-verified.
* Every ``apply`` is atomic: all validation, kernel execution, result re-verification and effect computation
  run on a working copy of the state; only ``applied`` / ``no_effect`` outcomes commit (once).  A ledger-level
  rejection leaves cash, lots, capacity, orders, dedup registries, sequence/times and the state hash untouched
  and is recorded only as an append-only audit entry, so a corrected event may reuse its identity.
* Events are applied in strictly increasing ``sequence`` and non-decreasing ``executed_at``.  Replaying the
  same event identity **and** payload is an idempotent skip; the same identity with different content is a
  conflict.  An order's decision content and order terms (limit, phase, submission, eligibility, expiry) are
  bound at first registration; later attempts may only vary attempt-time evidence and reduce the remaining
  quantity - anything else is ``order_terms_conflict`` and expiry is enforced from the original contract.
  Cumulative fills of an order never exceed its first declared quantity.
* Everything returned (``apply`` records, ``records``, ``snapshot``) is a detached deep copy; mutating it
  cannot touch stored history, evidence registries or hashes.
* Capacity is a shared resource per ``capacity_id`` across orders: share budgets consume shares; CNY budgets
  consume the money actually spent at each fill's own price, and the residual is presented to the kernel
  through a declared, audited adapter (never re-priced at the next fill).
* Acquisition fees enter lot cost; sale fees leave realized PnL; partial-lot disposals allocate cost with
  ROUND_HALF_UP cents and the final disposal clears the exact remaining cost, so cost is conserved to the
  cent.  All arithmetic runs under the kernel's fixed Decimal context.
* Appending later events never changes earlier event records or state hashes (chronological prefix
  invariance).  The ledger performs no valuation: marks are not part of this step (M4-02B interface only).
"""
from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import dataclass, replace
from datetime import datetime
from decimal import ROUND_FLOOR, ROUND_HALF_UP, Decimal, localcontext
from typing import Any

LEDGER_CONTRACT_VERSION = "0.1.0-draft"
LEDGER_NAMESPACE = "m4.portfolio"
CENT = Decimal("0.01")

EVENT_APPLIED = "applied"
EVENT_NO_EFFECT = "no_effect"
EVENT_SKIPPED_DUPLICATE = "skipped_duplicate"
EVENT_REJECTED = "rejected"
EVENT_STATUSES = (EVENT_APPLIED, EVENT_NO_EFFECT, EVENT_SKIPPED_DUPLICATE, EVENT_REJECTED)

LEDGER_REJECT_CODES = (
    "invalid_event", "sequence_not_increasing", "event_out_of_order", "duplicate_event_conflict", "attempt_identity_conflict",
    "account_ref_mismatch", "account_state_mismatch", "account_state_stale", "policy_hash_mismatch", "order_identity_conflict",
    "order_terms_conflict", "order_not_live", "order_quantity_exceeds_remaining", "capacity_evidence_conflict", "capacity_rate_conflict",
    "capacity_consumption_mismatch", "expected_result_hash_mismatch", "kernel_result_inconsistent", "invariant_violation",
)

_POLICY_SOURCE: dict[str, Any] = {
    "namespace": LEDGER_NAMESPACE,
    "contract_version": LEDGER_CONTRACT_VERSION,
    "kernel": {"module": "backend/app/research/m4_execution.py", "integration_revision": "M4-01-codex-integration-1",
               "policy_hash": "9bea83482d545e6f39dd8eb70e89d674dd5d900378b596c243da8e122c273e62", "injected": True},
    "units": {"quantity": "shares (int)", "money": "CNY Decimal quantized to 0.01", "capacity_share": "shares (int)",
              "capacity_cny": "CNY Decimal; budget = original amount x max_participation_rate; consumption = gross amount actually filled"},
    "state": ["cash", "lots[symbol] FIFO by (acquired_session, sequence): quantity_remaining, cost_remaining, provenance",
              "orders[order_id]: requested_total, filled_cumulative, remaining, live", "capacity[capacity_id]: unit, budget, consumed",
              "realized_pnl_total", "event_records with state_hash chain"],
    "account_state": "derived from the ledger for the requested symbol only (shared cash, that symbol's lots); request.account must equal "
                     "the derived state (money spellings normalized, lots aggregated per acquired session) and last_applied_executed_at <= as_of <= executed_at, "
                     "else rejected before execution; the frozen kernel's symbol-less InventoryLot tuple is adapted by the ledger, not changed",
    "atomicity": "all validation, kernel execution, result verification and effect computation run on a working copy; applied/no_effect commit once; "
                 "rejected commits nothing (no cash/lot/capacity/order/registry/sequence/time/state_hash change) and is only an append-only audit record",
    "views": "apply() records, records and snapshot() are detached deep copies; mutating them cannot alter stored history, evidence or hashes",
    "effects": {"filled/partially_filled": "cash += ledger_entry.cash_delta; buy creates one lot with cost = gross + commission + transfer_fee; "
                                           "sell consumes FIFO lots and realizes proceeds_net - allocated cost",
                "unfilled": "no_effect, committed (attempt registered, order liveness follows the kernel); kernel reasons kept",
                "kernel rejected": "no_effect, NOT committed (nothing happened: no registry, capacity, sequence or state-hash change; the event may be corrected and resubmitted); kernel reasons kept",
                "ledger_rejected": "rejected, NOT committed; ledger reasons kept as an append-only audit record"},
    "ordering": "sequence strictly increasing; executed_at non-decreasing across all recorded events",
    "idempotency": {"same event_id and same payload": "skipped_duplicate (no fees, no deltas)",
                    "same event_id and different payload": "rejected:duplicate_event_conflict",
                    "same (order_id, attempt_id) and same payload under another event_id": "skipped_duplicate",
                    "same (order_id, attempt_id) and different payload": "rejected:attempt_identity_conflict"},
    "orders": {"requested_total": "order.quantity of the first registered event for the order_id",
               "bound_terms": "decision content (canonical record) and order limit_price, execution_phase, submitted_at, eligible_from, expiry_sessions, decision_id are "
                              "bound at first registration; a later attempt with different bound terms is rejected:order_terms_conflict (symbol/side/decision_id: order_identity_conflict); "
                              "an amendment is a new order identity",
               "later attempts": "order.quantity must be <= remaining (a reduction is recorded as remaining_reduced_by_caller); > remaining is rejected",
               "liveness": "after a committed result with order_live_after_attempt=false (filled, expired window, final auction) further attempts are rejected:order_not_live; "
                           "expiry itself is enforced by the frozen kernel from the bound original terms on every attempt (order_expired -> no_effect, not committed)",
               "fees_per_attempt": "each partial execution is charged by the kernel per attempt, including the per-attempt minimum commission (disclosed assumption)"},
    "capacity": {"share": "kernel consumed_quantity is set by the ledger to the shares consumed so far under the same capacity_id; the event must carry 0 or the same value",
                 "CNY": "adapter: residual_amount = floor_cents((original_amount x rate - money_consumed) / rate) presented with consumed_quantity=0 and the original capacity_id/provenance; "
                        "money_consumed is the sum of gross amounts at each fill's own price; never re-priced",
                 "conflict": "a later event with the same capacity_id must carry identical evidence fields and the same participation rate"},
    "fifo": {"lot_cost": "gross + commission + transfer_fee (buy side)",
             "allocation": "partial disposal of a lot: round_half_up_cents(cost_remaining x matched / quantity_remaining); final disposal: exact cost_remaining",
             "realized_pnl": "proceeds_net (gross - commission - transfer_fee - stamp_duty) - sum(allocated cost)",
             "conservation": "sum of allocations over a lot's life == its original cost, to the cent"},
    "identities": {"payload_hash": "sha256(canonical kernel record of the request + expected_result_hash)",
                   "event_record_hash": "sha256(canonical event record without event_record_hash)",
                   "state_hash": "sha256(canonical state + previous state_hash)"},
    "valuation": "none in this step; marks must be supplied through an M4-02B interface with observed_at <= the decision instant they value",
    "m4_02b_interface": {
        "reads": ["account_state(as_of, symbol) -> kernel AccountState (shared cash, that symbol's FIFO lots by acquired session)", "positions() -> {symbol: shares}",
                  "settlement_view(session, calendar, sellable_after_sessions) -> settled/unsettled per symbol", "snapshot() -> full state + state_hash",
                  "records -> ordered event records with kernel identities, effects, capacity accounting", "reconcile() -> exact cash/position/cost checks"],
        "sizing": "produces kernel Order quantities (lot-conformant) from cash/positions above; must not read marks observed after the decision instant",
        "valuation_input": "{symbol, mark_price, observed_at, available_at, source_ref, kind} with observed_at <= decision instant; the ledger will not accept marks in this step",
        "risk": "maximum exposure, stop/exit priority, cooldown in exchange sessions and benchmark/delisting handling consume records and snapshot; not implemented here",
        "writes": "only through apply(AttemptEvent); no delta bypass",
    },
    "flags": {"review_only": True, "live_trading_enabled": False, "training_eligible": False, "M4_complete": False, "synthetic": "propagated from the kernel"},
    "not_implemented_here": ["position sizing", "maximum exposure", "stop-loss / exit selection", "cooldown", "benchmark", "delisting", "historical data"],
}


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False, default=_default)


def _default(value: Any) -> Any:
    if isinstance(value, Decimal):
        return str(value)
    raise TypeError(f"unserializable {type(value).__name__}")


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


LEDGER_POLICY: dict[str, Any] = json.loads(canonical_json(_POLICY_SOURCE))
LEDGER_POLICY_HASH = sha256_text(canonical_json(_POLICY_SOURCE))


class LedgerInputError(ValueError):
    def __init__(self, code: str, detail: str) -> None:
        super().__init__(f"{code}: {detail}")
        self.code, self.detail = code, detail


def _cents(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def _floor_cents(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_FLOOR)


def _money_str(value: Decimal) -> str:
    return str(_cents(value))


@dataclass(frozen=True)
class InitialLot:
    """Pre-existing inventory declared at ledger creation (synthetic; cost is declared, not derived)."""

    symbol: str
    quantity: int
    acquired_session: str
    cost: Any
    provenance_ref: str


@dataclass(frozen=True)
class AttemptEvent:
    """One explicitly ordered execution attempt for an already-sized order."""

    event_id: str
    sequence: int
    request: Any                      # kernel.ExecutionRequest (validated by the kernel)
    expected_result_hash: str | None = None
    note: str = ""


class _Reject(Exception):
    def __init__(self, code: str, detail: str, **extra: Any) -> None:
        super().__init__(code)
        self.code, self.detail, self.extra = code, detail, extra


class PortfolioLedger:
    """Deterministic in-memory ledger.  ``kernel`` is the injected frozen execution module.

    All mutable state lives in ``self._state`` and is only ever replaced wholesale by ``apply`` after a
    successful evaluation on a deep copy (transactional commit).  Every public read returns detached copies.
    """

    def __init__(self, kernel: Any, *, ledger_id: str, account_ref: str, initial_cash: Any, initial_lots: tuple[InitialLot, ...] = (),
                 expected_policy_hash: str | None = None, synthetic: bool = True) -> None:
        for attr in ("execute", "AccountState", "InventoryLot", "POLICY_HASH", "ARITHMETIC_CONTEXT", "canonical_json", "sha256_text", "_record"):
            if not hasattr(kernel, attr):
                raise LedgerInputError("invalid_kernel", f"injected kernel lacks {attr}")
        self.kernel = kernel
        self.ledger_id = _str(ledger_id, "ledger_id")
        self.account_ref = _str(account_ref, "account_ref")
        self.expected_policy_hash = expected_policy_hash or kernel.POLICY_HASH
        if self.expected_policy_hash != kernel.POLICY_HASH:
            raise LedgerInputError("policy_hash_mismatch", f"kernel policy {kernel.POLICY_HASH} != expected {self.expected_policy_hash}")
        self.synthetic = bool(synthetic)
        with localcontext(kernel.ARITHMETIC_CONTEXT):
            cash = _decimal(initial_cash, "initial_cash")
            if cash < 0 or cash != _cents(cash):
                raise LedgerInputError("invalid_initial_cash", f"initial cash must be >= 0 with 2 decimals, got {initial_cash!r}")
            self.initial_cash = _cents(cash)
            lots: dict[str, list[dict[str, Any]]] = {}
            initial_quantities: dict[str, int] = {}
            for i, lot in enumerate(initial_lots):
                if not isinstance(lot, InitialLot):
                    raise LedgerInputError("invalid_initial_lot", "initial_lots must be InitialLot")
                q = _int(lot.quantity, "initial lot quantity", minimum=1)
                cost = _cents(_decimal(lot.cost, "initial lot cost"))
                if cost < 0:
                    raise LedgerInputError("invalid_initial_lot", "cost must be >= 0")
                _str(lot.symbol, "initial lot symbol")
                _str(lot.provenance_ref, "initial lot provenance_ref")
                datetime.strptime(lot.acquired_session, "%Y-%m-%d")
                lots.setdefault(lot.symbol, []).append({
                    "lot_id": f"initial:{lot.symbol}:{i}", "symbol": lot.symbol, "acquired_session": lot.acquired_session,
                    "quantity_original": q, "quantity_remaining": q, "cost_original": _money_str(cost), "cost_remaining": _money_str(cost),
                    "fees_in_cost": None, "fill_price": None, "sellable_from_session": None,
                    "provenance": {"kind": "initial_declared", "provenance_ref": lot.provenance_ref, "event_id": None, "order_id": None,
                                   "attempt_id": None, "result_hash": None, "input_hash": None}, "created_sequence": 0})
                initial_quantities[lot.symbol] = initial_quantities.get(lot.symbol, 0) + q
            self.initial_quantities = initial_quantities
            self._state: dict[str, Any] = {
                "cash": self.initial_cash, "lots": lots, "orders": {}, "capacity": {}, "realized": [], "cash_deltas": [], "qty_deltas": {},
                "events_by_id": {}, "attempts": {}, "last_sequence": 0, "last_executed_at": None, "last_applied_executed_at": None,
            }
            self._records: list[dict[str, Any]] = []
            self._state_hash = sha256_text(canonical_json({"ledger_id": self.ledger_id, "genesis": self._state_body(self._state)}))
            self.genesis_state_hash = self._state_hash

    # ------------------------------------------------------------------ public views (all detached)
    @property
    def records(self) -> tuple[dict[str, Any], ...]:
        return tuple(copy.deepcopy(r) for r in self._records)

    @property
    def state_hash(self) -> str:
        return self._state_hash

    @property
    def last_sequence(self) -> int:
        return self._state["last_sequence"]

    @property
    def last_applied_executed_at(self) -> str | None:
        return self._state["last_applied_executed_at"]

    def account_state(self, as_of: str, symbol: str) -> Any:
        """The only legitimate way to build the kernel AccountState for the next attempt on ``symbol``: shared
        cash plus that symbol's FIFO lots (the kernel's InventoryLot is symbol-less, so pooling is never done)."""
        _str(symbol, "symbol")
        with localcontext(self.kernel.ARITHMETIC_CONTEXT):
            lots = tuple(self.kernel.InventoryLot(l["quantity_remaining"], l["acquired_session"]) for l in _fifo_lots(self._state, symbol))
            return self.kernel.AccountState(account_ref=self.account_ref, available_cash=_money_str(self._state["cash"]), inventory=lots, as_of=as_of,
                                            synthetic=self.synthetic)

    def positions(self) -> dict[str, int]:
        return _positions(self._state)

    def settlement_view(self, session: str, calendar: Any, sellable_after_sessions: int) -> dict[str, dict[str, int]]:
        """Settled / unsettled quantity per symbol at ``session`` on the injected calendar (same rule as the kernel)."""
        index = calendar.index()
        if session not in index:
            raise LedgerInputError("invalid_session", f"{session} not in calendar")
        out: dict[str, dict[str, int]] = {}
        for sym, lots in sorted(self._state["lots"].items()):
            settled = sum(l["quantity_remaining"] for l in lots if l["acquired_session"] in index and index[l["acquired_session"]] + sellable_after_sessions <= index[session])
            total = sum(l["quantity_remaining"] for l in lots)
            if total:
                out[sym] = {"held_total": total, "settled_sellable": settled, "unsettled": total - settled}
        return out

    def snapshot(self) -> dict[str, Any]:
        with localcontext(self.kernel.ARITHMETIC_CONTEXT):
            body = self._state_body(self._state)
        snap = {"schema": f"{LEDGER_NAMESPACE}.snapshot.v1", "ledger_id": self.ledger_id, "ledger_policy_hash": LEDGER_POLICY_HASH,
                "kernel_policy_hash": self.expected_policy_hash, **body, "state_hash": self._state_hash, "records": len(self._records),
                "review_only": True, "live_trading_enabled": False, "training_eligible": False, "M4_complete": False, "synthetic": self.synthetic}
        return copy.deepcopy(snap)

    def reconcile(self) -> dict[str, Any]:
        """Exact reconciliation: cash vs initial + applied deltas; positions vs initial + applied fills; cost conservation."""
        st = self._state
        with localcontext(self.kernel.ARITHMETIC_CONTEXT):
            expected_cash = self.initial_cash + sum(st["cash_deltas"], Decimal("0.00"))
            positions = {}
            for sym in sorted(set(self.initial_quantities) | set(st["qty_deltas"]) | set(st["lots"])):
                held = sum(l["quantity_remaining"] for l in st["lots"].get(sym, []))
                expected = self.initial_quantities.get(sym, 0) + st["qty_deltas"].get(sym, 0)
                positions[sym] = {"held": held, "expected": expected, "ok": held == expected}
            acquisitions = sum((Decimal(l["cost_original"]) for lots in st["lots"].values() for l in lots), Decimal("0.00"))
            allocated = sum((Decimal(r["cost_allocated"]) for r in st["realized"]), Decimal("0.00"))
            remaining = sum((Decimal(l["cost_remaining"]) for lots in st["lots"].values() for l in lots), Decimal("0.00"))
            realized_total = sum((Decimal(r["realized_pnl"]) for r in st["realized"]), Decimal("0.00"))
            proceeds_total = sum((Decimal(r["proceeds_net"]) for r in st["realized"]), Decimal("0.00"))
            result = {"cash": {"ledger": _money_str(st["cash"]), "initial_plus_deltas": _money_str(expected_cash), "ok": st["cash"] == expected_cash,
                               "applied_deltas": len(st["cash_deltas"]), "non_negative": st["cash"] >= 0},
                      "positions": positions, "positions_ok": all(v["ok"] for v in positions.values()) and all(l["quantity_remaining"] >= 0 for lots in st["lots"].values() for l in lots),
                      "cost": {"acquisitions": _money_str(acquisitions), "allocated_to_sales": _money_str(allocated), "remaining_in_lots": _money_str(remaining),
                               "ok": acquisitions == allocated + remaining},
                      "realized_pnl": {"total": _money_str(realized_total), "proceeds_net_minus_allocated": _money_str(proceeds_total - allocated),
                                       "ok": realized_total == proceeds_total - allocated},
                      "capacity": {cid: {"unit": c["unit"], "budget": c["budget"], "consumed": c["consumed"], "within_budget": Decimal(c["consumed"]) <= Decimal(c["budget"])}
                                   for cid, c in sorted(st["capacity"].items())}}
            result["ok"] = bool(result["cash"]["ok"] and result["cash"]["non_negative"] and result["positions_ok"] and result["cost"]["ok"]
                                and result["realized_pnl"]["ok"] and all(c["within_budget"] for c in result["capacity"].values()))
            return copy.deepcopy(result)

    # ------------------------------------------------------------------ apply (transactional)
    def apply(self, event: AttemptEvent) -> dict[str, Any]:
        """Apply one event atomically.  Never raises for domain problems; returns a detached event record."""
        with localcontext(self.kernel.ARITHMETIC_CONTEXT):
            work = copy.deepcopy(self._state)
            base: dict[str, Any] = {"schema": f"{LEDGER_NAMESPACE}.event_record.v1", "ledger_id": self.ledger_id, "event_id": None, "sequence": None,
                                    "status": None, "reasons": [], "state_hash_before": self._state_hash}
            try:
                status, reasons, commit = self._evaluate(event, work, base)
            except _Reject as exc:
                status, reasons, commit = EVENT_REJECTED, [{"code": exc.code, "detail": exc.detail, **exc.extra}], False
            if commit:
                self._state = work                                                    # single commit point
                self._state_hash = sha256_text(canonical_json({"previous": self._state_hash, "state": self._state_body(self._state)}))
            base["status"], base["reasons"] = status, reasons
            base["committed"] = commit
            base["state_hash_after"] = self._state_hash
            base["state_after"] = {"cash": _money_str(self._state["cash"]), "positions": _positions(self._state), "realized_pnl_total": _realized_total(self._state)}
            base["review_only"], base["live_trading_enabled"] = True, False
            base["event_record_hash"] = sha256_text(canonical_json({k: v for k, v in base.items() if k != "event_record_hash"}))
            record = json.loads(canonical_json(base))
        self._records.append(record)
        return copy.deepcopy(record)

    # ------------------------------------------------------------------ internals (operate on ``work`` only)
    def _evaluate(self, event: AttemptEvent, work: dict[str, Any], base: dict[str, Any]) -> tuple[str, list[dict[str, Any]], bool]:
        """Returns (status, reasons, commit).  Commit is True only for kernel filled / partially_filled / unfilled
        results: those attempts happened.  A kernel-rejected attempt (nothing happened) and every ledger-level
        rejection commit nothing - no registry, capacity, sequence or state-hash change."""
        if not isinstance(event, AttemptEvent):
            raise _Reject("invalid_event", "event must be AttemptEvent")
        base["event_id"] = event.event_id if isinstance(event.event_id, str) else None
        base["sequence"] = event.sequence if isinstance(event.sequence, int) and not isinstance(event.sequence, bool) else None
        _str(event.event_id, "event_id", reject=True)
        if base["sequence"] is None:
            raise _Reject("invalid_event", "sequence must be int")
        if event.expected_result_hash is not None and not (isinstance(event.expected_result_hash, str) and len(event.expected_result_hash) == 64):
            raise _Reject("invalid_event", "expected_result_hash must be a 64-hex string or None")
        req = event.request
        try:
            req.validated()
        except Exception as exc:  # noqa: BLE001 - kernel input errors become ledger rejections
            raise _Reject("invalid_event", f"request failed kernel validation: {exc}") from exc
        payload_hash = sha256_text(canonical_json({"request": self.kernel._record(req), "expected_result_hash": event.expected_result_hash}))
        base["payload_hash"] = payload_hash
        order_id, attempt_id, symbol = req.order.order_id, req.attempt.attempt_id, req.order.symbol
        base["identity"] = {"order_id": order_id, "attempt_id": attempt_id, "symbol": symbol, "side": req.order.side, "executed_at": req.attempt.executed_at}
        # ---- idempotency and conflicts (before ordering, so a replay is a skip rather than an ordering error)
        if event.event_id in work["events_by_id"]:
            if work["events_by_id"][event.event_id] == payload_hash:
                return EVENT_SKIPPED_DUPLICATE, [{"code": "duplicate_event", "detail": "same event_id and payload already recorded; no effect"}], False
            raise _Reject("duplicate_event_conflict", f"event_id {event.event_id} already recorded with a different payload")
        seen = work["attempts"].get(f"{order_id}\u0000{attempt_id}")
        if seen is not None:
            if seen["payload_hash"] == payload_hash:
                return EVENT_SKIPPED_DUPLICATE, [{"code": "duplicate_attempt", "detail": f"attempt {order_id}/{attempt_id} already recorded under event {seen['event_id']}; no effect"}], False
            raise _Reject("attempt_identity_conflict", f"attempt {order_id}/{attempt_id} already recorded with different content (event {seen['event_id']})")
        # ---- ordering
        if event.sequence <= work["last_sequence"]:
            raise _Reject("sequence_not_increasing", f"sequence {event.sequence} <= last {work['last_sequence']}")
        executed_at = _instant(req.attempt.executed_at)
        if work["last_executed_at"] is not None and executed_at < _instant(work["last_executed_at"]):
            raise _Reject("event_out_of_order", f"executed_at {req.attempt.executed_at} precedes last recorded {work['last_executed_at']}")
        # ---- account state must be the ledger's own, for this symbol
        if req.account.account_ref != self.account_ref:
            raise _Reject("account_ref_mismatch", f"{req.account.account_ref!r} != ledger account {self.account_ref!r}")
        as_of = _instant(req.account.as_of)
        if work["last_applied_executed_at"] is not None and as_of < _instant(work["last_applied_executed_at"]):
            raise _Reject("account_state_stale", f"account as_of {req.account.as_of} precedes the last applied execution {work['last_applied_executed_at']}")
        if as_of > executed_at:
            raise _Reject("account_state_stale", f"account as_of {req.account.as_of} is after executed_at {req.attempt.executed_at}")
        derived = self.account_state(req.account.as_of, symbol)
        supplied_key, derived_key = _account_key(self.kernel, req.account), _account_key(self.kernel, derived)
        if supplied_key != derived_key:
            raise _Reject("account_state_mismatch", f"supplied account state differs from the ledger-derived state for {symbol}",
                          supplied=supplied_key, derived=derived_key)
        # ---- order registry: immutable terms bound at first registration
        terms = _order_terms(self.kernel, req)
        order = work["orders"].get(order_id)
        reduced = None
        if order is None:
            order_view = {"symbol": symbol, "side": req.order.side, "decision_id": req.order.decision_id, "requested_total": req.order.quantity,
                          "filled_cumulative": 0, "remaining": req.order.quantity, "live": True, "terms": terms,
                          "terms_hash": sha256_text(canonical_json(terms)), "attempts": []}
        else:
            if (order["symbol"], order["side"], order["decision_id"]) != (symbol, req.order.side, req.order.decision_id):
                raise _Reject("order_identity_conflict", f"order {order_id} previously {order['symbol']}/{order['side']}/{order['decision_id']}")
            changed = sorted(k for k in terms if terms[k] != order["terms"][k])
            if changed:
                raise _Reject("order_terms_conflict", f"order {order_id} attempt changes bound terms {changed}; an amendment needs a new order identity",
                              changed=changed, bound=order["terms"])
            if not order["live"]:
                raise _Reject("order_not_live", f"order {order_id} is complete or no longer live ({order['filled_cumulative']}/{order['requested_total']} filled)")
            if req.order.quantity > order["remaining"]:
                raise _Reject("order_quantity_exceeds_remaining", f"attempt quantity {req.order.quantity} > remaining {order['remaining']} of {order['requested_total']}")
            if req.order.quantity < order["remaining"]:
                reduced = {"remaining_before": order["remaining"], "attempt_quantity": req.order.quantity}
            order_view = copy.deepcopy(order)
        # ---- capacity adapter (nothing is committed here; the budget is written into ``work`` only)
        effective_capacity, capacity_note = self._capacity_for(req, work)
        effective = replace(req, account=derived, capacity=effective_capacity)
        base["effective_request"] = {"account_derived_for_symbol": symbol, "capacity_adapter": capacity_note}
        # ---- execute the frozen kernel and re-verify its result
        result = self.kernel.execute(effective)
        rec = result.record
        self._verify_result(rec, req)
        if event.expected_result_hash is not None and rec["result_hash"] != event.expected_result_hash:
            raise _Reject("expected_result_hash_mismatch", f"kernel result {rec['result_hash']} != expected {event.expected_result_hash}")
        base["kernel"] = {"status": rec["status"], "reasons": rec["reasons"], "result_hash": rec["result_hash"], "input_hash": rec["identities"]["input_hash"],
                          "policy_hash": rec["policy_hash"], "contract_version": rec["contract_version"], "order_live_after_attempt": rec["order_live_after_attempt"],
                          "evidence_grade": (rec.get("evidence") or {}).get("evidence_grade"), "synthetic": rec["synthetic"]}
        if rec["status"] == "rejected":
            # nothing happened at the kernel: no registry, order, capacity, sequence or hash change; the audit record still names the order/attempt
            base["order"] = {k: v for k, v in order_view.items() if k not in ("attempts", "terms")}
            return EVENT_NO_EFFECT, [{"code": "kernel_rejected", "detail": "no cash, position or registry effect; the event was not committed and may be corrected and resubmitted",
                                     "kernel_reasons": rec["reasons"]}], False
        # ---- effects on the working copy (committed as a whole by apply)
        work["events_by_id"][event.event_id] = payload_hash
        work["attempts"][f"{order_id}\u0000{attempt_id}"] = {"payload_hash": payload_hash, "event_id": event.event_id}
        work["last_sequence"] = event.sequence
        work["last_executed_at"] = req.attempt.executed_at
        order_view["attempts"].append({"event_id": event.event_id, "attempt_id": attempt_id, "status": rec["status"], "filled": rec["fill"]["filled_quantity"]})
        if rec["status"] in ("filled", "partially_filled"):
            effects = self._apply_fill(event, req, rec, work)
            order_view["filled_cumulative"] += rec["fill"]["filled_quantity"]
            order_view["remaining"] = order_view["requested_total"] - order_view["filled_cumulative"] if reduced is None else req.order.quantity - rec["fill"]["filled_quantity"]
            if reduced is not None:
                order_view["requested_total"] = order_view["filled_cumulative"] + order_view["remaining"]
                effects["remaining_reduced_by_caller"] = reduced
            order_view["live"] = bool(rec["order_live_after_attempt"]) and order_view["remaining"] > 0
            work["orders"][order_id] = order_view
            work["last_applied_executed_at"] = req.attempt.executed_at
            _check_invariants(work)
            base["effects"] = effects
            base["order"] = {k: v for k, v in order_view.items() if k not in ("attempts", "terms")}
            return EVENT_APPLIED, [], True
        # unfilled: the attempt happened; liveness follows the kernel (expiry window, final auction)
        if reduced is not None:
            order_view["remaining"] = req.order.quantity
            order_view["requested_total"] = order_view["filled_cumulative"] + req.order.quantity
            base["effects"] = {"remaining_reduced_by_caller": reduced}
        order_view["live"] = bool(rec["order_live_after_attempt"]) and order_view["remaining"] > 0
        work["orders"][order_id] = order_view
        base["order"] = {k: v for k, v in order_view.items() if k not in ("attempts", "terms")}
        return EVENT_NO_EFFECT, [{"code": "kernel_unfilled", "detail": "no cash or position effect; attempt registered", "kernel_reasons": rec["reasons"]}], True

    def _capacity_for(self, req: Any, work: dict[str, Any]) -> tuple[Any, dict[str, Any] | None]:
        cap = req.capacity
        if cap is None:
            return None, None
        rate = Decimal(str(req.assumptions.max_participation_rate)).normalize()
        fields = {"symbol": cap.symbol, "quantity": _norm(cap.quantity) if cap.unit == "CNY" else cap.quantity, "unit": cap.unit, "basis": cap.basis,
                  "observed_at": cap.observed_at, "available_at": cap.available_at, "source_ref": cap.source_ref, "kind": cap.kind, "assumption_ref": cap.assumption_ref}
        budget = work["capacity"].get(cap.capacity_id)
        if budget is None:
            if cap.consumed_quantity != 0:
                raise _Reject("capacity_consumption_mismatch", f"first use of capacity {cap.capacity_id} must carry consumed_quantity=0, got {cap.consumed_quantity}")
            if cap.unit == "share":
                budget = {"capacity_id": cap.capacity_id, "unit": "share", "evidence": fields, "rate": str(rate), "original_quantity": cap.quantity,
                          "budget": str(int((Decimal(cap.quantity) * rate).to_integral_value(rounding=ROUND_FLOOR))), "consumed": "0", "fills": []}
            else:
                amount = Decimal(_norm(cap.quantity))
                budget = {"capacity_id": cap.capacity_id, "unit": "CNY", "evidence": fields, "rate": str(rate), "original_amount": str(amount),
                          "budget": _money_str(_floor_cents(amount * rate)), "consumed": "0.00", "fills": []}
            work["capacity"][cap.capacity_id] = budget
        else:
            if budget["evidence"] != fields:
                raise _Reject("capacity_evidence_conflict", f"capacity {cap.capacity_id} evidence differs from its first use", first=budget["evidence"], now=fields)
            if budget["rate"] != str(rate):
                raise _Reject("capacity_rate_conflict", f"participation rate {rate} != {budget['rate']} first declared for {cap.capacity_id}")
        if cap.unit == "share":
            consumed = int(budget["consumed"])
            if cap.consumed_quantity not in (0, consumed):
                raise _Reject("capacity_consumption_mismatch", f"event carries consumed_quantity={cap.consumed_quantity}; ledger tracks {consumed} for {cap.capacity_id}")
            return replace(cap, consumed_quantity=consumed), {"capacity_id": cap.capacity_id, "unit": "share", "consumed_shares_injected": consumed,
                                                                "budget_shares": budget["budget"], "rule": "kernel consumed_quantity = ledger shares consumed"}
        if cap.consumed_quantity != 0:
            raise _Reject("capacity_consumption_mismatch", f"CNY capacity {cap.capacity_id} must carry consumed_quantity=0; the ledger tracks money consumed")
        money_consumed = Decimal(budget["consumed"])
        remaining_money = Decimal(budget["budget"]) - money_consumed
        residual = _floor_cents(remaining_money / rate) if remaining_money > 0 else Decimal("0.00")
        note = {"capacity_id": cap.capacity_id, "unit": "CNY", "original_amount": budget["original_amount"], "rate": budget["rate"], "budget_money": budget["budget"],
                "money_consumed_before": _money_str(money_consumed), "remaining_money": _money_str(remaining_money), "residual_amount_presented": _money_str(residual),
                "rule": "residual_amount = floor_cents((original_amount x rate - money_consumed) / rate); presented with consumed_quantity=0; original capacity_id and provenance kept"}
        return replace(cap, quantity=_money_str(residual), consumed_quantity=0), note

    def _verify_result(self, rec: dict[str, Any], req: Any) -> None:
        k = self.kernel
        body = {key: v for key, v in rec.items() if key != "result_hash"}
        if k.sha256_text(k.canonical_json(body)) != rec["result_hash"]:
            raise _Reject("kernel_result_inconsistent", "result_hash does not recompute")
        if rec["policy_hash"] != self.expected_policy_hash or rec["identities"]["policy_hash"] != self.expected_policy_hash:
            raise _Reject("policy_hash_mismatch", f"result policy {rec['policy_hash']} != expected {self.expected_policy_hash}")
        ident = rec["identity"]
        if (ident["order_id"], ident["attempt_id"], ident["symbol"], ident["side"]) != (req.order.order_id, req.attempt.attempt_id, req.order.symbol, req.order.side):
            raise _Reject("kernel_result_inconsistent", "result identity differs from the request")
        if rec["status"] in ("filled", "partially_filled"):
            f, le = rec["fill"], rec["ledger_entry"]
            if not f["fill_recorded"] or le is None:
                raise _Reject("kernel_result_inconsistent", "fill status without a recorded fill")
            fees = {key: Decimal(v) for key, v in f["fees"].items()}
            if fees["commission"] + fees["transfer_fee"] + fees["stamp_duty"] != fees["total"]:
                raise _Reject("kernel_result_inconsistent", "fee breakdown does not sum")
            gross = Decimal(f["gross_amount"])
            if _cents(Decimal(f["fill_price"]) * f["filled_quantity"]) != gross:
                raise _Reject("kernel_result_inconsistent", "gross != fill_price x quantity")
            expected_delta = -(gross + fees["total"]) if req.order.side == "buy" else gross - fees["total"]
            if Decimal(le["cash_delta"]) != expected_delta or le["quantity_delta"] != (f["filled_quantity"] if req.order.side == "buy" else -f["filled_quantity"]):
                raise _Reject("kernel_result_inconsistent", "ledger_entry deltas do not match the fill")
            if f["filled_quantity"] > req.order.quantity or f["filled_quantity"] <= 0:
                raise _Reject("kernel_result_inconsistent", "filled quantity outside (0, requested]")
        elif rec["fill"]["fill_recorded"] or rec["ledger_entry"] is not None or rec["fill"]["filled_quantity"] != 0:
            raise _Reject("kernel_result_inconsistent", "non-fill status carries fill effects")

    def _apply_fill(self, event: AttemptEvent, req: Any, rec: dict[str, Any], work: dict[str, Any]) -> dict[str, Any]:
        f, le = rec["fill"], rec["ledger_entry"]
        symbol, side, filled = req.order.symbol, req.order.side, f["filled_quantity"]
        gross, fees = Decimal(f["gross_amount"]), {key: Decimal(v) for key, v in f["fees"].items()}
        cash_delta = Decimal(le["cash_delta"])
        cash_before = work["cash"]
        effects: dict[str, Any] = {"symbol": symbol, "side": side, "filled_quantity": filled, "fill_price": f["fill_price"], "gross_amount": f["gross_amount"],
                                   "fees": f["fees"], "cash_delta": le["cash_delta"], "cash_before": _money_str(cash_before)}
        cap = req.capacity
        if cap is not None:
            budget = work["capacity"][cap.capacity_id]
            if cap.unit == "share":
                consumed_after = int(budget["consumed"]) + filled
                if f["capacity"]["consumed_after"] != consumed_after:
                    raise _Reject("kernel_result_inconsistent", "kernel consumed_after != ledger consumed + filled")
                if consumed_after > int(budget["budget"]):
                    raise _Reject("invariant_violation", f"share budget overspent: {consumed_after} > {budget['budget']}")
                budget["consumed"] = str(consumed_after)
            else:
                consumed_after = Decimal(budget["consumed"]) + gross
                if consumed_after > Decimal(budget["budget"]):
                    raise _Reject("invariant_violation", f"CNY budget overspent: {consumed_after} > {budget['budget']}")
                budget["consumed"] = _money_str(consumed_after)
            budget["fills"].append({"event_id": event.event_id, "order_id": req.order.order_id, "attempt_id": req.attempt.attempt_id, "filled_quantity": filled,
                                    "fill_price": f["fill_price"], "gross_amount": f["gross_amount"], "consumed_after": budget["consumed"]})
            effects["capacity"] = {"capacity_id": cap.capacity_id, "unit": cap.unit, "budget": budget["budget"], "consumed_after": budget["consumed"]}
        if cash_before + cash_delta < 0:
            raise _Reject("invariant_violation", "cash would go negative")
        if side == "buy":
            cost = _cents(gross + fees["commission"] + fees["transfer_fee"])
            lot = {"lot_id": f"{symbol}:{req.order.order_id}:{req.attempt.attempt_id}", "symbol": symbol, "acquired_session": le["session"],
                   "quantity_original": filled, "quantity_remaining": filled, "cost_original": _money_str(cost), "cost_remaining": _money_str(cost),
                   "fees_in_cost": _money_str(fees["commission"] + fees["transfer_fee"]), "fill_price": f["fill_price"], "sellable_from_session": le["sellable_from_session"],
                   "provenance": {"kind": "kernel_fill", "provenance_ref": None, "event_id": event.event_id, "order_id": req.order.order_id,
                                  "attempt_id": req.attempt.attempt_id, "result_hash": rec["result_hash"], "input_hash": rec["identities"]["input_hash"]},
                   "created_sequence": event.sequence}
            work["lots"].setdefault(symbol, []).append(lot)
            effects.update({"lot_created": {k: v for k, v in lot.items() if k != "provenance"}, "quantity_delta": filled})
        else:
            available = sum(l["quantity_remaining"] for l in work["lots"].get(symbol, []))
            if filled > available:
                raise _Reject("invariant_violation", f"sell {filled} of {symbol} exceeds held {available}")
            remaining, allocations, allocated_total = filled, [], Decimal("0.00")
            for lot in _fifo_lots(work, symbol):
                if remaining == 0:
                    break
                matched = min(remaining, lot["quantity_remaining"])
                cost_remaining = Decimal(lot["cost_remaining"])
                if matched == lot["quantity_remaining"]:
                    allocated, disposal = cost_remaining, "full"
                else:
                    allocated, disposal = _cents(cost_remaining * Decimal(matched) / Decimal(lot["quantity_remaining"])), "partial"
                lot["quantity_remaining"] -= matched
                lot["cost_remaining"] = _money_str(cost_remaining - allocated)
                allocations.append({"lot_id": lot["lot_id"], "acquired_session": lot["acquired_session"], "matched_quantity": matched, "cost_allocated": _money_str(allocated),
                                    "disposal": disposal, "lot_quantity_after": lot["quantity_remaining"], "lot_cost_after": lot["cost_remaining"]})
                allocated_total += allocated
                remaining -= matched
            proceeds_net = gross - fees["total"]
            realized = _cents(proceeds_net - allocated_total)
            sale = {"event_id": event.event_id, "order_id": req.order.order_id, "attempt_id": req.attempt.attempt_id, "symbol": symbol, "session": le["session"],
                    "quantity": filled, "fill_price": f["fill_price"], "gross_amount": f["gross_amount"], "fees": f["fees"], "proceeds_net": _money_str(proceeds_net),
                    "cost_allocated": _money_str(allocated_total), "realized_pnl": _money_str(realized), "lots": allocations, "result_hash": rec["result_hash"]}
            work["realized"].append(sale)
            effects.update({"sale": sale, "quantity_delta": -filled})
        work["cash"] = _cents(cash_before + cash_delta)
        effects["cash_after"] = _money_str(work["cash"])
        if effects["cash_after"] != le["cash_after"]:
            raise _Reject("kernel_result_inconsistent", f"ledger cash {effects['cash_after']} != kernel cash_after {le['cash_after']}")
        work["cash_deltas"].append(cash_delta)
        work["qty_deltas"][symbol] = work["qty_deltas"].get(symbol, 0) + effects["quantity_delta"]
        return effects

    def _state_body(self, st: dict[str, Any]) -> dict[str, Any]:
        return {"cash": _money_str(st["cash"]), "positions": _positions(st),
                "lots": {sym: [dict(l) for l in sorted(lots, key=lambda l: (l["acquired_session"], l["created_sequence"], l["lot_id"]))] for sym, lots in sorted(st["lots"].items())},
                "orders": {oid: {k: v for k, v in o.items() if k != "attempts"} for oid, o in sorted(st["orders"].items())},
                "capacity": {cid: {k: v for k, v in c.items() if k != "fills"} for cid, c in sorted(st["capacity"].items())},
                "realized_pnl_total": _realized_total(st), "sales": len(st["realized"]), "last_sequence": st["last_sequence"],
                "last_executed_at": st["last_executed_at"], "last_applied_executed_at": st["last_applied_executed_at"]}


def _fifo_lots(st: dict[str, Any], symbol: str) -> list[dict[str, Any]]:
    return sorted((l for l in st["lots"].get(symbol, []) if l["quantity_remaining"] > 0), key=lambda l: (l["acquired_session"], l["created_sequence"], l["lot_id"]))


def _positions(st: dict[str, Any]) -> dict[str, int]:
    return {sym: sum(l["quantity_remaining"] for l in lots) for sym, lots in sorted(st["lots"].items()) if any(l["quantity_remaining"] for l in lots)}


def _realized_total(st: dict[str, Any]) -> str:
    return _money_str(sum((Decimal(r["realized_pnl"]) for r in st["realized"]), Decimal("0.00")))


def _check_invariants(work: dict[str, Any]) -> None:
    if work["cash"] < 0:
        raise _Reject("invariant_violation", "negative cash")
    for lots in work["lots"].values():
        for lot in lots:
            if lot["quantity_remaining"] < 0 or Decimal(lot["cost_remaining"]) < 0:
                raise _Reject("invariant_violation", f"negative lot {lot['lot_id']}")


def _order_terms(kernel: Any, req: Any) -> dict[str, Any]:
    """Immutable terms bound to an order id at first registration (everything except the attempt-time evidence and quantity)."""
    o = kernel._record(req.order)
    return {"decision": kernel._record(req.decision), "decision_id": o["decision_id"], "symbol": o["symbol"], "side": o["side"], "limit_price": o["limit_price"],
            "submitted_at": o["submitted_at"], "eligible_from": o["eligible_from"], "expiry_sessions": o["expiry_sessions"], "execution_phase": o["execution_phase"],
            "instrument": kernel._record(req.instrument), "calendar_source_ref": req.calendar.source_ref}


# ---------------------------------------------------------------------- helpers
def _str(value: Any, what: str, *, reject: bool = False) -> str:
    if not isinstance(value, str) or not value.strip():
        if reject:
            raise _Reject("invalid_event", f"{what} must be a non-empty string")
        raise LedgerInputError("invalid_input", f"{what} must be a non-empty string, got {value!r}")
    return value


def _int(value: Any, what: str, *, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise LedgerInputError("invalid_input", f"{what} must be an int >= {minimum}, got {value!r}")
    return value


def _decimal(value: Any, what: str) -> Decimal:
    if isinstance(value, bool) or isinstance(value, float):
        raise LedgerInputError("invalid_input", f"{what} must be Decimal, int or decimal string (not float/bool), got {value!r}")
    try:
        d = Decimal(value) if not isinstance(value, str) else Decimal(value.strip())
    except Exception as exc:  # noqa: BLE001
        raise LedgerInputError("invalid_input", f"{what} is not a number: {value!r}") from exc
    if not d.is_finite():
        raise LedgerInputError("invalid_input", f"{what} must be finite")
    return d


def _norm(value: Any) -> str:
    return format(Decimal(str(value)).normalize(), "f")


def _instant(text: str) -> datetime:
    dt = datetime.fromisoformat(text[:-1] + "+00:00" if text.endswith("Z") else text)
    if dt.tzinfo is None:
        raise _Reject("invalid_event", f"naive instant {text}")
    return dt


def _account_key(kernel: Any, account: Any) -> dict[str, Any]:
    """Semantic account content: cash (normalized spelling), inventory aggregated per acquired session, ref, synthetic."""
    rec = kernel._record(account)
    by_session: dict[str, int] = {}
    for lot in rec["inventory"]:
        by_session[lot["acquired_session"]] = by_session.get(lot["acquired_session"], 0) + lot["quantity"]
    rec["inventory"] = dict(sorted(by_session.items()))
    rec.pop("as_of", None)
    return rec


__all__ = ["LEDGER_CONTRACT_VERSION", "LEDGER_POLICY", "LEDGER_POLICY_HASH", "LEDGER_REJECT_CODES", "EVENT_STATUSES", "LedgerInputError",
           "InitialLot", "AttemptEvent", "PortfolioLedger", "canonical_json", "sha256_text"]
