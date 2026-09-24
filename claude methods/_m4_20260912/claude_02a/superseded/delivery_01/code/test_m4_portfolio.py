"""Standalone unittest suite for ``backend/app/research/m4_portfolio.py`` (M4-02A) over the frozen M4-01 kernel.

Run with the project interpreter (stdlib unittest; both modules loaded by file path; no ``app`` import, no
conftest, no pytest, no SQLite, no network, no clock):

    backend/.venv/Scripts/python.exe -B -X utf8 backend/tests/test_m4_portfolio.py -v

All fixtures are synthetic (``SYN_*`` symbols, ``syn:`` refs, ``synthetic=True``).  The fee schedule
``HYPOTHETICAL_LEDGER_FEES`` (buy/sell commission 0.0003 with a 5.00 minimum, transfer 0.00001, sell stamp
0.0005) and the assumptions (zero slippage, participation 1 unless stated, tick 0.01, 100-share lots,
T+1) are arithmetic fixtures, not real tariffs.  Every expected number is hand-calculated in the comments.
``LEDGER_LOG`` collects the per-scenario event records, snapshot and reconciliation for the runner to dump.
"""
from __future__ import annotations

import ast
import decimal
import hashlib
import importlib.util
import json
import sys
import unittest
from dataclasses import replace
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

BACKEND = Path(__file__).resolve().parents[1]
KERNEL_PATH = BACKEND / "app" / "research" / "m4_execution.py"
LEDGER_PATH = BACKEND / "app" / "research" / "m4_portfolio.py"
FROZEN_KERNEL_SHA256 = "83a28b543b9ecc5edf8080ea39fa388f8b2bb5a8724ef68b4b532041216678c7"
FROZEN_KERNEL_POLICY_HASH = "9bea83482d545e6f39dd8eb70e89d674dd5d900378b596c243da8e122c273e62"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


k = _load("m4_execution_frozen_for_ledger_tests", KERNEL_PATH)
p = _load("m4_portfolio_under_test", LEDGER_PATH)

LEDGER_LOG: dict[str, dict] = {}

SYM = "SYN_LEDGER_01"
SYM2 = "SYN_LEDGER_02"
SESSIONS = ("2024-03-18", "2024-03-19", "2024-03-20", "2024-03-21", "2024-03-22", "2024-03-25")
CAL = k.SessionCalendar(SESSIONS, "+08:00", "09:30", "15:00", "syn:calendar", "2024-01-01T00:00:00+08:00", True)
FEES = k.FeeSchedule("HYPOTHETICAL_LEDGER_FEES", "fixture-1", "hypothetical_fixture", "syn:fee-fixture", "2024-01-01", None, ("syn_main",),
                     "0.0003", "0.0003", "5.00", "0.00001", "0.0005")


def assumptions(rate="1"):
    return k.ExecutionAssumptions("HYPOTHETICAL_LEDGER_ASSUMPTIONS", "hypothetical_fixture", "syn:assumption-fixture", "0", rate, "0.01",
                                  k.LotPolicy("syn:lot_100", 100, 100, 100, "whole_odd_remainder_only", 1_000_000), k.SettlementPolicy("syn:T+1", 1))


def instrument(symbol=SYM):
    return k.Instrument(symbol, "stock", "syn_main", "syn:listing", "syn:calendar", True)


def prev_session(session: str) -> str:
    return SESSIONS[SESSIONS.index(session) - 1]


def request(ledger, side, quantity, price, session, order_id, attempt_id, *, limit=None, symbol=SYM, at="09:30:00", phase="open_auction",
            capacity_id="CAP-1", capacity_qty=100_000, capacity_unit="share", consumed=0, rate="1", expiry=1, as_of=None, account=None,
            eligible_at="09:30:00", decision_session=None, capacity_at=None):
    """A prior-close decision (previous session) executed at ``session``.  The account state is derived from the
    ledger unless given, as of 09:00 of the session or the last applied execution instant, whichever is later.
    ``capacity_at`` pins the capacity evidence observation time (one evidence window may serve several attempts)."""
    dsession = decision_session or prev_session(session)
    t = f"{session}T{at}+08:00"
    ct = f"{session}T{capacity_at or at}+08:00"
    eligible = f"{session}T{eligible_at}+08:00"
    cap_qty = capacity_qty if capacity_unit == "share" else str(capacity_qty)
    if account is None and as_of is None:
        default_as_of = f"{session}T09:00:00+08:00"
        last = ledger.last_applied_executed_at
        as_of = last if last is not None and last > default_as_of else default_as_of
    acct = account if account is not None else ledger.account_state(as_of)
    return k.ExecutionRequest(
        decision=k.Decision(f"D-{order_id}", symbol, side, dsession, f"{dsession}T16:00:00+08:00",
                            (k.InputAvailability("prior_close", f"{dsession}T15:05:00+08:00", "syn:bar"),), "syn:rule"),
        order=k.Order(order_id, f"D-{order_id}", symbol, side, quantity, limit or price, f"{session}T09:00:00+08:00", eligible, expiry, phase),
        instrument=instrument(symbol), calendar=CAL,
        tradability=k.TradabilityEvidence(symbol, session, "tradable", "none", "band", "20.00", "5.00", "not_st", "seasoned",
                                          f"{session}T09:15:00+08:00", f"{session}T09:15:00+08:00", "syn:tradability", True),
        price=k.PriceObservation(symbol, price, "open_auction_print" if phase == "open_auction" else "last_trade", t, t, "syn:price", "contemporaneous", True),
        capacity=k.LiquidityCapacity(symbol, capacity_id, cap_qty, capacity_unit, "auction_matched_quantity", ct, ct, "syn:capacity", "contemporaneous", True,
                                     consumed_quantity=consumed),
        account=acct, fee_schedule=FEES, assumptions=assumptions(rate), attempt=k.ExecutionAttempt(attempt_id, t, session, phase))


def ledger(cash="10000.00", lots=(), ledger_id="SYN-LEDGER", account_ref="SYN-ACCOUNT"):
    return p.PortfolioLedger(k, ledger_id=ledger_id, account_ref=account_ref, initial_cash=cash, initial_lots=tuple(lots))


def event(event_id, sequence, req, expected=None):
    return p.AttemptEvent(event_id, sequence, req, expected)


def log(name: str, L) -> None:
    LEDGER_LOG[name] = {"records": list(L.records), "snapshot": L.snapshot(), "reconcile": L.reconcile()}


class LedgerCase(unittest.TestCase):
    def assertApplied(self, rec):
        self.assertEqual(rec["status"], "applied", rec["reasons"])

    def assertRejectedWith(self, rec, code):
        self.assertEqual(rec["status"], "rejected", rec)
        self.assertEqual(rec["reasons"][0]["code"], code, rec["reasons"])

    def assertNoEffect(self, rec, kernel_code):
        self.assertEqual(rec["status"], "no_effect", rec)
        self.assertIn(kernel_code, [r["code"] for r in rec["reasons"][0]["kernel_reasons"]], rec["reasons"])


# ======================================================================================
class TestHandAnchorRoundTrip(LedgerCase):
    def test_round_trip_matches_the_hand_anchor(self):
        L = ledger("10000.00")
        r1 = L.apply(event("E1", 1, request(L, "buy", 100, "10.00", "2024-03-19", "O-BUY", "A1")))
        self.assertApplied(r1)
        # buy 100 x 10.00 = 1000.00; commission max(0.30, 5.00) = 5.00; transfer 0.01 -> cost 1005.01; cash 8994.99
        self.assertEqual(r1["effects"]["fees"], {"commission": "5.00", "transfer_fee": "0.01", "stamp_duty": "0.00", "total": "5.01"})
        self.assertEqual(r1["effects"]["cash_delta"], "-1005.01")
        self.assertEqual(r1["state_after"], {"cash": "8994.99", "positions": {SYM: 100}, "realized_pnl_total": "0.00"})
        lot = r1["effects"]["lot_created"]
        self.assertEqual((lot["quantity_remaining"], lot["cost_remaining"], lot["fees_in_cost"], lot["acquired_session"], lot["sellable_from_session"]),
                         (100, "1005.01", "5.01", "2024-03-19", "2024-03-20"))
        r2 = L.apply(event("E2", 2, request(L, "sell", 100, "11.00", "2024-03-20", "O-SELL", "A1", capacity_id="CAP-2")))
        self.assertApplied(r2)
        # sell 100 x 11.00 = 1100.00; commission 5.00; transfer 0.01; stamp 0.55 -> proceeds 1094.44; realized 1094.44 - 1005.01 = 89.43
        sale = r2["effects"]["sale"]
        self.assertEqual(sale["fees"], {"commission": "5.00", "transfer_fee": "0.01", "stamp_duty": "0.55", "total": "5.56"})
        self.assertEqual((sale["proceeds_net"], sale["cost_allocated"], sale["realized_pnl"]), ("1094.44", "1005.01", "89.43"))
        self.assertEqual(sale["lots"][0]["disposal"], "full")
        self.assertEqual(r2["state_after"], {"cash": "10089.43", "positions": {}, "realized_pnl_total": "89.43"})
        rec = L.reconcile()
        self.assertTrue(rec["ok"], rec)
        self.assertEqual(rec["cash"]["initial_plus_deltas"], "10089.43")
        self.assertEqual(rec["cost"], {"acquisitions": "1005.01", "allocated_to_sales": "1005.01", "remaining_in_lots": "0.00", "ok": True})
        snap = L.snapshot()
        self.assertEqual((snap["cash"], snap["positions"], snap["realized_pnl_total"]), ("10089.43", {}, "89.43"))
        self.assertTrue(snap["review_only"] and not snap["live_trading_enabled"] and not snap["training_eligible"] and not snap["M4_complete"])
        log("anchor.round_trip", L)

    def test_records_carry_kernel_identities_and_hash_chain(self):
        L = ledger()
        req = request(L, "buy", 100, "10.00", "2024-03-19", "O1", "A1")
        direct = k.execute(req)                         # the same request run directly through the frozen kernel
        r = L.apply(event("E1", 1, req))
        self.assertEqual(r["kernel"]["result_hash"], direct.result_hash)
        self.assertEqual(r["kernel"]["input_hash"], direct.record["identities"]["input_hash"])
        self.assertEqual(r["kernel"]["policy_hash"], FROZEN_KERNEL_POLICY_HASH)
        lot = L.lots[SYM][0]
        self.assertEqual(lot["provenance"], {"kind": "kernel_fill", "provenance_ref": None, "event_id": "E1", "order_id": "O1", "attempt_id": "A1",
                                             "result_hash": direct.result_hash, "input_hash": direct.record["identities"]["input_hash"]})
        self.assertNotEqual(r["state_hash_before"], r["state_hash_after"])
        self.assertEqual(r["state_hash_before"], L.genesis_state_hash)
        body = {key: v for key, v in r.items() if key != "event_record_hash"}
        self.assertEqual(r["event_record_hash"], p.sha256_text(p.canonical_json(body)))
        self.assertEqual(r["payload_hash"], p.sha256_text(p.canonical_json({"request": k._record(req), "expected_result_hash": None})))


# ======================================================================================
class TestFIFOCostAllocation(LedgerCase):
    def test_multi_lot_partial_sale_conserves_cost_to_the_cent(self):
        L = ledger("10000.00")
        self.assertApplied(L.apply(event("E1", 1, request(L, "buy", 100, "10.00", "2024-03-19", "O1", "A1"))))          # lot1 cost 1005.01
        r2 = L.apply(event("E2", 2, request(L, "buy", 300, "10.33", "2024-03-20", "O2", "A1", capacity_id="CAP-2")))
        self.assertApplied(r2)
        # 300 x 10.33 = 3099.00; commission max(0.9297 -> 0.93, 5.00) = 5.00; transfer 0.03099 -> 0.03; lot2 cost 3104.03
        self.assertEqual(r2["effects"]["lot_created"]["cost_remaining"], "3104.03")
        self.assertEqual(L.snapshot()["cash"], "5890.96")                                                         # 10000 - 1005.01 - 3104.03
        r3 = L.apply(event("E3", 3, request(L, "sell", 200, "12.00", "2024-03-21", "O3", "A1", capacity_id="CAP-3")))
        self.assertApplied(r3)
        sale = r3["effects"]["sale"]
        # 200 x 12.00 = 2400.00; commission max(0.72, 5.00) = 5.00; transfer 0.024 -> 0.02; stamp 1.20 -> fees 6.22; proceeds 2393.78
        self.assertEqual(sale["fees"], {"commission": "5.00", "transfer_fee": "0.02", "stamp_duty": "1.20", "total": "6.22"})
        self.assertEqual(sale["proceeds_net"], "2393.78")
        # FIFO: lot1 fully disposed (1005.01); lot2 partial 100/300 -> 3104.03 x 100 / 300 = 1034.6766... -> 1034.68 (ROUND_HALF_UP)
        self.assertEqual([(a["lot_id"], a["matched_quantity"], a["cost_allocated"], a["disposal"]) for a in sale["lots"]],
                         [(f"{SYM}:O1:A1", 100, "1005.01", "full"), (f"{SYM}:O2:A1", 100, "1034.68", "partial")])
        self.assertEqual(sale["cost_allocated"], "2039.69")
        self.assertEqual(sale["realized_pnl"], "354.09")                                                          # 2393.78 - 2039.69
        self.assertEqual(L.lots[SYM][1]["cost_remaining"], "2069.35")                                              # 3104.03 - 1034.68
        self.assertEqual(L.lots[SYM][1]["quantity_remaining"], 200)
        r4 = L.apply(event("E4", 4, request(L, "sell", 200, "12.00", "2024-03-22", "O4", "A1", capacity_id="CAP-4")))
        self.assertApplied(r4)
        sale4 = r4["effects"]["sale"]
        self.assertEqual(sale4["lots"], [{"lot_id": f"{SYM}:O2:A1", "acquired_session": "2024-03-20", "matched_quantity": 200, "cost_allocated": "2069.35",
                                          "disposal": "full", "lot_quantity_after": 0, "lot_cost_after": "0.00"}])
        self.assertEqual(sale4["realized_pnl"], "324.43")                                                         # 2393.78 - 2069.35 (final disposal clears the exact remainder)
        self.assertEqual(L.snapshot()["realized_pnl_total"], "678.52")                                            # 354.09 + 324.43
        self.assertEqual(L.snapshot()["cash"], "10678.52")                                                        # 5890.96 + 2393.78 x 2 = 10000 + 678.52
        rec = L.reconcile()
        self.assertTrue(rec["ok"], rec)
        self.assertEqual(rec["cost"], {"acquisitions": "4109.04", "allocated_to_sales": "4109.04", "remaining_in_lots": "0.00", "ok": True})
        log("fifo.multi_lot_partial", L)

    def test_declared_initial_lot_participates_in_fifo(self):
        L = ledger("1000.00", lots=(p.InitialLot(SYM, 100, "2024-03-18", "950.00", "syn:opening-position"),))
        self.assertEqual(L.positions(), {SYM: 100})
        r = L.apply(event("E1", 1, request(L, "sell", 100, "10.00", "2024-03-19", "O1", "A1")))
        self.assertApplied(r)
        # proceeds 1000.00 - 5.00 - 0.01 - 0.50 = 994.49; realized 994.49 - 950.00 = 44.49
        self.assertEqual(r["effects"]["sale"]["realized_pnl"], "44.49")
        self.assertEqual(r["effects"]["sale"]["lots"][0]["lot_id"], f"initial:{SYM}:0")
        self.assertEqual(L.lots[SYM][0]["provenance"]["kind"], "initial_declared")
        self.assertTrue(L.reconcile()["ok"])


# ======================================================================================
class TestSettlementTPlusOne(LedgerCase):
    def test_t_plus_one_blocks_only_unsettled_lots(self):
        L = ledger("10000.00", lots=(p.InitialLot(SYM, 100, "2024-03-18", "1000.00", "syn:opening-position"),))
        self.assertApplied(L.apply(event("E1", 1, request(L, "buy", 200, "10.00", "2024-03-19", "O-BUY", "A1"))))   # same-session lot
        self.assertEqual(L.settlement_view("2024-03-19", CAL, 1), {SYM: {"held_total": 300, "settled_sellable": 100, "unsettled": 200}})
        over = L.apply(event("E2", 2, request(L, "sell", 150, "10.00", "2024-03-19", "O-S1", "A1", capacity_id="CAP-2")))
        self.assertNoEffect(over, "insufficient_settled_inventory")
        self.assertEqual(over["state_after"]["positions"], {SYM: 300})
        ok = L.apply(event("E3", 3, request(L, "sell", 100, "10.00", "2024-03-19", "O-S2", "A1", capacity_id="CAP-3")))
        self.assertApplied(ok)
        self.assertEqual(ok["effects"]["sale"]["lots"][0]["lot_id"], f"initial:{SYM}:0")     # FIFO takes the settled old lot
        self.assertEqual(L.settlement_view("2024-03-19", CAL, 1), {SYM: {"held_total": 200, "settled_sellable": 0, "unsettled": 200}})
        self.assertEqual(L.settlement_view("2024-03-20", CAL, 1), {SYM: {"held_total": 200, "settled_sellable": 200, "unsettled": 0}})
        nxt = L.apply(event("E4", 4, request(L, "sell", 200, "10.00", "2024-03-20", "O-S3", "A1", capacity_id="CAP-4")))
        self.assertApplied(nxt)
        self.assertEqual(L.positions(), {})
        self.assertTrue(L.reconcile()["ok"])
        log("settlement.mixed_inventory", L)


# ======================================================================================
class TestPartialFillsAndOrders(LedgerCase):
    def continuous(self, L, quantity, at, attempt_id, capacity_id="CAP-C", capacity_qty=150, seq_session="2024-03-19", capacity_at="10:00:00"):
        return request(L, "buy", quantity, "10.00", seq_session, "O-PART", attempt_id, at=at, phase="continuous", capacity_id=capacity_id,
                       capacity_qty=capacity_qty, as_of=f"{seq_session}T{at}+08:00", capacity_at=capacity_at)

    def test_partial_fill_remaining_order_and_per_attempt_fees(self):
        L = ledger("10000.00")
        r1 = L.apply(event("E1", 1, self.continuous(L, 300, "10:00:00", "A1")))
        self.assertApplied(r1)
        self.assertEqual(r1["kernel"]["status"], "partially_filled")
        self.assertEqual(r1["effects"]["filled_quantity"], 100)                 # allowance 150 -> one whole lot
        self.assertEqual(r1["effects"]["fees"]["commission"], "5.00")          # per-attempt minimum commission
        self.assertEqual(r1["order"], {"symbol": SYM, "side": "buy", "decision_id": "D-O-PART", "requested_total": 300, "filled_cumulative": 100, "remaining": 200, "live": True})
        # retry against the same capacity evidence: 50 shares remain -> below one lot -> unfilled, order stays live
        r2 = L.apply(event("E2", 2, self.continuous(L, 200, "11:00:00", "A2")))
        self.assertNoEffect(r2, "capacity_below_minimum_lot")
        self.assertTrue(r2["order"]["live"])
        self.assertEqual(r2["effective_request"]["capacity_adapter"]["consumed_shares_injected"], 100)
        # an attempt for more than the remaining 200 is refused before execution
        r3 = L.apply(event("E3", 3, self.continuous(L, 300, "11:30:00", "A3")))
        self.assertRejectedWith(r3, "order_quantity_exceeds_remaining")
        # fresh capacity evidence at 11:45 fills the remaining 200 (second minimum commission charged: disclosed per-attempt fee contract)
        r4 = L.apply(event("E4", 4, self.continuous(L, 200, "11:45:00", "A4", capacity_id="CAP-D", capacity_qty=500, capacity_at="11:45:00")))
        self.assertApplied(r4)
        self.assertEqual(r4["effects"]["fees"], {"commission": "5.00", "transfer_fee": "0.02", "stamp_duty": "0.00", "total": "5.02"})
        self.assertEqual(r4["order"], {"symbol": SYM, "side": "buy", "decision_id": "D-O-PART", "requested_total": 300, "filled_cumulative": 300, "remaining": 0, "live": False})
        self.assertEqual(L.snapshot()["cash"], "6989.97")                           # 10000 - 1005.01 - 2005.02
        self.assertEqual(L.positions(), {SYM: 300})
        r5 = L.apply(event("E5", 5, self.continuous(L, 100, "12:00:00", "A5", capacity_id="CAP-E", capacity_qty=500, capacity_at="12:00:00")))
        self.assertRejectedWith(r5, "order_not_live")
        self.assertEqual(L.positions(), {SYM: 300})
        self.assertTrue(L.reconcile()["ok"])
        log("orders.partial_and_remaining", L)

    def test_caller_may_reduce_the_remainder_but_never_exceed_it(self):
        L = ledger("10000.00")
        self.assertApplied(L.apply(event("E1", 1, self.continuous(L, 300, "10:00:00", "A1"))))
        r = L.apply(event("E2", 2, self.continuous(L, 100, "11:00:00", "A2", capacity_id="CAP-D", capacity_qty=500, capacity_at="11:00:00")))
        self.assertApplied(r)
        self.assertEqual(r["effects"]["remaining_reduced_by_caller"], {"remaining_before": 200, "attempt_quantity": 100})
        self.assertEqual(r["order"]["requested_total"], 200)
        self.assertEqual(r["order"]["filled_cumulative"], 200)
        self.assertFalse(r["order"]["live"])


# ======================================================================================
class TestIdempotencyAndConflicts(LedgerCase):
    def test_replay_is_an_idempotent_skip_and_conflicts_are_explicit(self):
        L = ledger("10000.00")
        req = request(L, "buy", 100, "10.00", "2024-03-19", "O1", "A1")
        r1 = L.apply(event("E1", 1, req))
        self.assertApplied(r1)
        replay = L.apply(event("E1", 1, req))
        self.assertEqual(replay["status"], "skipped_duplicate")
        self.assertEqual(replay["reasons"][0]["code"], "duplicate_event")
        self.assertEqual(replay["state_after"]["cash"], "8994.99")                  # fees not charged twice
        self.assertEqual(replay["state_hash_after"], r1["state_hash_after"])
        same_attempt = L.apply(event("E1-bis", 2, req))
        self.assertEqual(same_attempt["status"], "skipped_duplicate")
        self.assertEqual(same_attempt["reasons"][0]["code"], "duplicate_attempt")
        conflict = L.apply(event("E1", 2, replace(req, order=replace(req.order, quantity=200))))
        self.assertRejectedWith(conflict, "duplicate_event_conflict")
        attempt_conflict = L.apply(event("E9", 2, replace(req, price=replace(req.price, price="10.01"), order=replace(req.order, limit_price="10.01"))))
        self.assertRejectedWith(attempt_conflict, "attempt_identity_conflict")
        self.assertEqual(L.snapshot()["cash"], "8994.99")
        self.assertEqual(L.positions(), {SYM: 100})
        self.assertEqual([r["status"] for r in L.records], ["applied", "skipped_duplicate", "skipped_duplicate", "rejected", "rejected"])
        self.assertTrue(L.reconcile()["ok"])
        log("idempotency.replays", L)


# ======================================================================================
class TestOrderingAndMalformedEvents(LedgerCase):
    def test_sequence_and_time_ordering(self):
        L = ledger("10000.00")
        self.assertApplied(L.apply(event("E1", 5, request(L, "buy", 100, "10.00", "2024-03-20", "O1", "A1"))))
        low_seq = L.apply(event("E2", 5, request(L, "buy", 100, "10.00", "2024-03-21", "O2", "A1", capacity_id="CAP-2")))
        self.assertRejectedWith(low_seq, "sequence_not_increasing")
        earlier = L.apply(event("E3", 6, request(L, "buy", 100, "10.00", "2024-03-19", "O3", "A1", capacity_id="CAP-3", as_of="2024-03-19T09:00:00+08:00")))
        self.assertRejectedWith(earlier, "event_out_of_order")
        self.assertEqual(L.snapshot()["cash"], "8994.99")
        ok = L.apply(event("E4", 6, request(L, "buy", 100, "10.00", "2024-03-21", "O4", "A1", capacity_id="CAP-4")))
        self.assertApplied(ok)

    def test_malformed_events_are_rejected_without_effect(self):
        L = ledger("10000.00")
        bad_seq = L.apply(p.AttemptEvent("E1", "1", request(L, "buy", 100, "10.00", "2024-03-19", "O1", "A1")))
        self.assertRejectedWith(bad_seq, "invalid_event")
        bad_id = L.apply(p.AttemptEvent("", 1, request(L, "buy", 100, "10.00", "2024-03-19", "O1", "A1")))
        self.assertRejectedWith(bad_id, "invalid_event")
        naive = request(L, "buy", 100, "10.00", "2024-03-19", "O1", "A1")
        naive = replace(naive, attempt=replace(naive.attempt, executed_at="2024-03-19T09:30:00"))
        self.assertRejectedWith(L.apply(p.AttemptEvent("E2", 1, naive)), "invalid_event")
        self.assertRejectedWith(L.apply(p.AttemptEvent("E3", 1, request(L, "buy", 100, "10.00", "2024-03-19", "O1", "A1"), expected_result_hash="abc")), "invalid_event")
        self.assertRejectedWith(L.apply("not an event"), "invalid_event")
        self.assertEqual(L.snapshot()["cash"], "10000.00")
        self.assertEqual(L.last_sequence, 0)


# ======================================================================================
class TestAccountStateGuard(LedgerCase):
    def test_external_state_must_match_the_ledger(self):
        L = ledger("10000.00")
        stale = L.account_state("2024-03-19T09:00:00+08:00")
        self.assertApplied(L.apply(event("E1", 1, request(L, "buy", 100, "10.00", "2024-03-19", "O1", "A1"))))
        r = L.apply(event("E2", 2, request(L, "buy", 100, "10.00", "2024-03-20", "O2", "A1", capacity_id="CAP-2", account=replace(stale, as_of="2024-03-20T09:00:00+08:00"))))
        self.assertRejectedWith(r, "account_state_mismatch")
        self.assertEqual(r["reasons"][0]["supplied"]["available_cash"], "10000")
        self.assertEqual(r["reasons"][0]["derived"]["available_cash"], "8994.99")
        wrong_ref = replace(L.account_state("2024-03-20T09:00:00+08:00"), account_ref="OTHER")
        self.assertRejectedWith(L.apply(event("E3", 2, request(L, "buy", 100, "10.00", "2024-03-20", "O2", "A1", capacity_id="CAP-2", account=wrong_ref))), "account_ref_mismatch")
        stale_time = L.account_state("2024-03-19T09:00:00+08:00")               # content right, as_of before the last applied execution
        self.assertRejectedWith(L.apply(event("E4", 2, request(L, "buy", 100, "10.00", "2024-03-20", "O2", "A1", capacity_id="CAP-2", account=stale_time))), "account_state_stale")
        future = L.account_state("2024-03-20T09:30:01+08:00")
        self.assertRejectedWith(L.apply(event("E5", 2, request(L, "buy", 100, "10.00", "2024-03-20", "O2", "A1", capacity_id="CAP-2", account=future))), "account_state_stale")
        # equivalent spellings / merged lots are the same state
        merged = k.AccountState("SYN-ACCOUNT", Decimal("8994.99"), (k.InventoryLot(100, "2024-03-19"),), "2024-03-20T09:00:00+08:00", True)
        self.assertApplied(L.apply(event("E6", 2, request(L, "buy", 100, "10.00", "2024-03-20", "O2", "A1", capacity_id="CAP-2", account=merged))))
        self.assertEqual(L.snapshot()["cash"], "7989.98")
        log("account_guard", L)

    def test_public_surface_has_no_delta_bypass(self):
        public = sorted(n for n in dir(p.PortfolioLedger) if not n.startswith("_") and callable(getattr(p.PortfolioLedger, n)))
        self.assertEqual(public, ["account_state", "apply", "positions", "reconcile", "settlement_view", "snapshot"])


# ======================================================================================
class TestResultIntegrity(LedgerCase):
    def test_expected_result_hash_is_enforced(self):
        L = ledger("10000.00")
        req = request(L, "buy", 100, "10.00", "2024-03-19", "O1", "A1")
        good = k.execute(req).result_hash
        bad = L.apply(event("E1", 1, req, expected="0" * 64))
        self.assertRejectedWith(bad, "expected_result_hash_mismatch")
        self.assertEqual(L.snapshot()["cash"], "10000.00")
        self.assertApplied(L.apply(event("E2", 1, req, expected=good)))

    def test_tampered_kernel_results_are_refused(self):
        class TamperingKernel:
            def __init__(self, real, mutate):
                self.real, self.mutate = real, mutate
                for attr in ("AccountState", "InventoryLot", "POLICY_HASH", "ARITHMETIC_CONTEXT", "canonical_json", "sha256_text", "_record"):
                    setattr(self, attr, getattr(real, attr))

            def execute(self, request):
                record = json.loads(json.dumps(self.real.execute(request).record))
                self.mutate(record)
                return SimpleNamespace(record=record, status=record["status"])

        def more_cash(rec):        # cash delta altered, hash left as is -> hash no longer recomputes
            rec["ledger_entry"]["cash_delta"] = "-1.00"

        def rehashed_delta(rec):   # cash delta altered and hash recomputed -> internal inconsistency caught
            rec["ledger_entry"]["cash_delta"] = "-1.00"
            body = {key: v for key, v in rec.items() if key != "result_hash"}
            rec["result_hash"] = k.sha256_text(k.canonical_json(body))

        def wrong_policy(rec):
            rec["policy_hash"] = rec["identities"]["policy_hash"] = "1" * 64
            body = {key: v for key, v in rec.items() if key != "result_hash"}
            rec["result_hash"] = k.sha256_text(k.canonical_json(body))

        for name, mutate, code in (("hash_stale", more_cash, "kernel_result_inconsistent"), ("delta_rehashed", rehashed_delta, "kernel_result_inconsistent"),
                                   ("policy", wrong_policy, "policy_hash_mismatch")):
            with self.subTest(name):
                L = p.PortfolioLedger(TamperingKernel(k, mutate), ledger_id="SYN-TAMPER", account_ref="SYN-ACCOUNT", initial_cash="10000.00", expected_policy_hash=k.POLICY_HASH)
                r = L.apply(event("E1", 1, request(L, "buy", 100, "10.00", "2024-03-19", "O1", "A1")))
                self.assertRejectedWith(r, code)
                self.assertEqual(L.snapshot()["cash"], "10000.00")
                self.assertEqual(L.positions(), {})


# ======================================================================================
class TestSharedCapacity(LedgerCase):
    def test_share_budget_is_shared_across_orders(self):
        L = ledger("100000.00")
        r1 = L.apply(event("E1", 1, request(L, "buy", 300, "10.00", "2024-03-19", "O1", "A1", capacity_id="CAP-S", capacity_qty=500)))
        self.assertApplied(r1)
        self.assertEqual(r1["effects"]["capacity"], {"capacity_id": "CAP-S", "unit": "share", "budget": "500", "consumed_after": "300"})
        r2 = L.apply(event("E2", 2, request(L, "buy", 300, "10.00", "2024-03-19", "O2", "A1", capacity_id="CAP-S", capacity_qty=500)))
        self.assertApplied(r2)
        self.assertEqual(r2["kernel"]["status"], "partially_filled")
        self.assertEqual(r2["effects"]["filled_quantity"], 200)                                     # 500 - 300 = 200 left
        self.assertEqual(r2["effective_request"]["capacity_adapter"]["consumed_shares_injected"], 300)
        r3 = L.apply(event("E3", 3, request(L, "buy", 100, "10.00", "2024-03-19", "O3", "A1", capacity_id="CAP-S", capacity_qty=500)))
        self.assertNoEffect(r3, "capacity_exhausted")
        self.assertEqual(L.positions(), {SYM: 500})
        wrong_consumed = L.apply(event("E4", 4, request(L, "buy", 100, "10.00", "2024-03-19", "O4", "A1", capacity_id="CAP-S", capacity_qty=500, consumed=999)))
        self.assertRejectedWith(wrong_consumed, "capacity_consumption_mismatch")
        reset_attempt = L.apply(event("E5", 5, request(L, "buy", 100, "10.00", "2024-03-19", "O5", "A1", capacity_id="CAP-S", capacity_qty=900)))
        self.assertRejectedWith(reset_attempt, "capacity_evidence_conflict")
        rate_conflict = L.apply(event("E6", 6, request(L, "buy", 100, "10.00", "2024-03-19", "O6", "A1", capacity_id="CAP-S", capacity_qty=500, rate="0.5")))
        self.assertRejectedWith(rate_conflict, "capacity_rate_conflict")
        rec = L.reconcile()
        self.assertEqual(rec["capacity"]["CAP-S"], {"unit": "share", "budget": "500", "consumed": "500", "within_budget": True})
        self.assertTrue(rec["ok"])
        log("capacity.shares_shared", L)

    def test_cny_budget_consumes_money_at_each_fills_own_price(self):
        L = ledger("100000.00")
        cap = dict(capacity_id="CAP-M", capacity_qty="5000.00", capacity_unit="CNY", capacity_at="09:30:00")
        r1 = L.apply(event("E1", 1, request(L, "buy", 300, "10.00", "2024-03-19", "O1", "A1", **cap)))
        self.assertApplied(r1)
        self.assertEqual(r1["effective_request"]["capacity_adapter"]["residual_amount_presented"], "5000.00")
        self.assertEqual(r1["effects"]["capacity"], {"capacity_id": "CAP-M", "unit": "CNY", "budget": "5000.00", "consumed_after": "3000.00"})
        # second order at a different price: remaining money 2000.00 -> floor(2000 / 10.50) = 190 -> one whole lot of 100 (1050.00)
        r2 = L.apply(event("E2", 2, request(L, "buy", 300, "10.50", "2024-03-19", "O2", "A1", at="10:00:00", phase="continuous", as_of="2024-03-19T10:00:00+08:00", **cap)))
        self.assertApplied(r2)
        adapter = r2["effective_request"]["capacity_adapter"]
        self.assertEqual((adapter["money_consumed_before"], adapter["remaining_money"], adapter["residual_amount_presented"]), ("3000.00", "2000.00", "2000.00"))
        self.assertEqual(r2["effects"]["filled_quantity"], 100)
        self.assertEqual(r2["effects"]["capacity"]["consumed_after"], "4050.00")
        # third order at 9.00: remaining 950.00 -> floor(950 / 9) = 105 -> 100 shares (900.00)
        r3 = L.apply(event("E3", 3, request(L, "buy", 100, "9.00", "2024-03-19", "O3", "A1", at="11:00:00", phase="continuous", as_of="2024-03-19T11:00:00+08:00", **cap)))
        self.assertApplied(r3)
        self.assertEqual(r3["effects"]["capacity"]["consumed_after"], "4950.00")
        # 50.00 left: floor(50 / 9) = 5 shares < one lot -> unfilled; the budget is never overspent
        r4 = L.apply(event("E4", 4, request(L, "buy", 100, "9.00", "2024-03-19", "O4", "A1", at="11:30:00", phase="continuous", as_of="2024-03-19T11:30:00+08:00", **cap)))
        self.assertNoEffect(r4, "capacity_below_minimum_lot")
        self.assertEqual(r4["effective_request"]["capacity_adapter"]["residual_amount_presented"], "50.00")
        rec = L.reconcile()
        self.assertEqual(rec["capacity"]["CAP-M"], {"unit": "CNY", "budget": "5000.00", "consumed": "4950.00", "within_budget": True})
        self.assertTrue(rec["ok"])
        self.assertEqual(L.positions(), {SYM: 500})
        # the naive kernel-only chaining would have re-priced consumed shares: 400 shares consumed at the third fill's 9.00 = 3600 of a 5000 budget,
        # leaving 1400 instead of 950 - the adapter is what prevents that overspend
        self.assertEqual(Decimal(rec["capacity"]["CAP-M"]["consumed"]), Decimal("3000.00") + Decimal("1050.00") + Decimal("900.00"))
        log("capacity.cny_money_budget", L)

    def test_cny_budget_with_participation_rate_below_one(self):
        L = ledger("100000.00")
        cap = dict(capacity_id="CAP-R", capacity_qty="10000.00", capacity_unit="CNY", rate="0.5", capacity_at="09:30:00")
        r1 = L.apply(event("E1", 1, request(L, "buy", 400, "10.00", "2024-03-19", "O1", "A1", **cap)))
        self.assertApplied(r1)
        adapter = r1["effective_request"]["capacity_adapter"]
        self.assertEqual((adapter["budget_money"], adapter["residual_amount_presented"]), ("5000.00", "10000.00"))   # budget 10000 x 0.5; residual = 5000 / 0.5
        self.assertEqual(r1["effects"]["capacity"]["consumed_after"], "4000.00")
        r2 = L.apply(event("E2", 2, request(L, "buy", 200, "10.00", "2024-03-19", "O2", "A1", at="10:00:00", phase="continuous", as_of="2024-03-19T10:00:00+08:00", **cap)))
        self.assertApplied(r2)
        self.assertEqual(r2["effective_request"]["capacity_adapter"]["residual_amount_presented"], "2000.00")   # (5000 - 4000) / 0.5
        self.assertEqual(r2["effects"]["filled_quantity"], 100)                                                # kernel allowance floor(2000 x 0.5 / 10) = 100
        self.assertEqual(L.reconcile()["capacity"]["CAP-R"]["consumed"], "5000.00")
        r3 = L.apply(event("E3", 3, request(L, "buy", 100, "10.00", "2024-03-19", "O3", "A1", at="11:00:00", phase="continuous", as_of="2024-03-19T11:00:00+08:00", **cap)))
        self.assertNoEffect(r3, "capacity_exhausted")


# ======================================================================================
class TestChronologyAndMultiSymbol(LedgerCase):
    @staticmethod
    def three_steps():
        """Event factories: each request derives its account state from the ledger at the moment it is built."""
        return [lambda L: event("E1", 1, request(L, "buy", 100, "10.00", "2024-03-19", "O1", "A1")),
                lambda L: event("E2", 2, request(L, "buy", 200, "12.00", "2024-03-19", "O2", "A1", symbol=SYM2, capacity_id="CAP-2")),
                lambda L: event("E3", 3, request(L, "sell", 100, "11.00", "2024-03-20", "O3", "A1", capacity_id="CAP-3"))]

    def test_appending_later_events_does_not_change_earlier_records_or_hashes(self):
        a = ledger("10000.00")
        for step in self.three_steps():
            self.assertApplied(a.apply(step(a)))
        prefix_records, prefix_snapshot = [dict(r) for r in a.records], a.snapshot()
        b = ledger("10000.00")
        for step in self.three_steps():
            self.assertApplied(b.apply(step(b)))
        self.assertEqual(b.snapshot(), prefix_snapshot)
        self.assertApplied(b.apply(event("E4", 4, request(b, "sell", 200, "13.00", "2024-03-21", "O4", "A1", symbol=SYM2, capacity_id="CAP-4"))))
        self.assertApplied(b.apply(event("E5", 5, request(b, "buy", 100, "10.00", "2024-03-22", "O5", "A1", capacity_id="CAP-5"))))
        self.assertEqual(b.records[:3], prefix_records)
        self.assertEqual([r["state_hash_after"] for r in b.records[:3]], [r["state_hash_after"] for r in prefix_records])
        self.assertNotEqual(b.snapshot()["state_hash"], prefix_snapshot["state_hash"])
        self.assertTrue(b.reconcile()["ok"])
        log("chronology.prefix", b)

    def test_multiple_symbols_keep_separate_lots(self):
        L = ledger("10000.00")
        for step in self.three_steps():
            self.assertApplied(L.apply(step(L)))
        # SYM2: 200 x 12.00 = 2400.00; commission max(0.72, 5.00) = 5.00; transfer 0.024 -> 0.02; cost 2405.02
        self.assertEqual(L.lots[SYM2][0]["cost_remaining"], "2405.02")
        self.assertEqual(L.positions(), {SYM2: 200})
        self.assertEqual(L.snapshot()["cash"], "7684.41")        # 10000 - 1005.01 - 2405.02 + 1094.44
        self.assertEqual(L.snapshot()["realized_pnl_total"], "89.43")
        rec = L.reconcile()
        self.assertEqual(rec["positions"], {SYM: {"held": 0, "expected": 0, "ok": True}, SYM2: {"held": 200, "expected": 200, "ok": True}})
        self.assertTrue(rec["ok"])


# ======================================================================================
class TestNoEffectResults(LedgerCase):
    def test_kernel_rejections_and_unfilled_results_leave_the_ledger_untouched(self):
        L = ledger("500.00")
        poor = L.apply(event("E1", 1, request(L, "buy", 100, "10.00", "2024-03-19", "O1", "A1")))
        self.assertNoEffect(poor, "insufficient_cash")
        self.assertTrue(L.orders["O1"]["live"])                                     # nothing happened; the order may be retried
        self.assertEqual(L.snapshot()["cash"], "500.00")
        susp = request(L, "buy", 100, "10.00", "2024-03-20", "O2", "A1", capacity_id="CAP-2", expiry=2)
        susp = replace(susp, tradability=replace(susp.tradability, status="suspended"))
        r = L.apply(event("E2", 2, susp))
        self.assertNoEffect(r, "suspended")
        self.assertTrue(r["order"]["live"])
        expired = request(L, "buy", 100, "10.00", "2024-03-21", "O3", "A1", capacity_id="CAP-3")
        expired = replace(expired, capacity=None)
        r3 = L.apply(event("E3", 3, expired))
        self.assertNoEffect(r3, "capacity_unproven")
        self.assertFalse(r3["order"]["live"])                                       # one-session open-auction order: final opportunity used
        self.assertRejectedWith(L.apply(event("E4", 4, request(L, "buy", 100, "10.00", "2024-03-22", "O3", "A2", capacity_id="CAP-4"))), "order_not_live")
        self.assertEqual(L.snapshot()["cash"], "500.00")
        self.assertEqual(L.positions(), {})
        rec = L.reconcile()
        self.assertTrue(rec["ok"])
        self.assertEqual(rec["cash"]["applied_deltas"], 0)
        log("no_effect.results", L)


# ======================================================================================
class TestNumericAndConstruction(LedgerCase):
    def test_caller_decimal_context_and_spelling_do_not_change_the_ledger(self):
        reference = ledger(Decimal("10000"))
        for step in TestChronologyAndMultiSymbol.three_steps():
            reference.apply(step(reference))
        with decimal.localcontext() as ctx:
            ctx.prec, ctx.rounding = 6, decimal.ROUND_DOWN
            ctx.traps[decimal.Inexact] = True
            L = ledger("10000.00")
            for step in TestChronologyAndMultiSymbol.three_steps():
                self.assertApplied(L.apply(step(L)))
            self.assertEqual(L.records, reference.records)
            self.assertEqual(L.snapshot(), reference.snapshot())
            self.assertEqual(ctx.prec, 6)
        self.assertEqual(L.genesis_state_hash, reference.genesis_state_hash)

    def test_construction_validation(self):
        with self.assertRaises(p.LedgerInputError):
            ledger("-1.00")
        with self.assertRaises(p.LedgerInputError):
            ledger(100.0)
        with self.assertRaises(p.LedgerInputError):
            ledger("100.005")
        with self.assertRaises(p.LedgerInputError):
            p.PortfolioLedger(k, ledger_id="X", account_ref="A", initial_cash="1.00", expected_policy_hash="0" * 64)
        with self.assertRaises(p.LedgerInputError):
            ledger("1.00", lots=(p.InitialLot(SYM, True, "2024-03-18", "1.00", "syn:x"),))
        with self.assertRaises(p.LedgerInputError):
            p.PortfolioLedger(SimpleNamespace(), ledger_id="X", account_ref="A", initial_cash="1.00")


# ======================================================================================
class TestPolicyAndIsolation(LedgerCase):
    def test_frozen_kernel_is_the_one_under_the_ledger(self):
        self.assertEqual(hashlib.sha256(KERNEL_PATH.read_bytes()).hexdigest(), FROZEN_KERNEL_SHA256)
        self.assertEqual(k.POLICY_HASH, FROZEN_KERNEL_POLICY_HASH)
        self.assertEqual(p.LEDGER_POLICY["kernel"]["policy_hash"], FROZEN_KERNEL_POLICY_HASH)
        self.assertEqual(len(p.LEDGER_POLICY_HASH), 64)
        self.assertEqual(p.LEDGER_POLICY_HASH, p.sha256_text(p.canonical_json(p.LEDGER_POLICY)))

    def test_module_is_stdlib_only_without_side_effects(self):
        tree = ast.parse(LEDGER_PATH.read_text(encoding="utf-8"))
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(a.name.split(".")[0] for a in node.names)
            elif isinstance(node, ast.ImportFrom):
                imported.add((node.module or "").split(".")[0])
        self.assertTrue(imported <= {"__future__", "hashlib", "json", "dataclasses", "datetime", "decimal", "typing"}, imported)
        calls = {n.func.attr if isinstance(n.func, ast.Attribute) else getattr(n.func, "id", None) for n in ast.walk(tree) if isinstance(n, ast.Call)}
        for forbidden in ("now", "utcnow", "today", "open", "getenv", "environ", "connect", "system", "popen", "run"):
            self.assertNotIn(forbidden, calls, forbidden)
        self.assertFalse(any(name == "app" or name.startswith("app.") for name in sys.modules))

    def test_every_status_and_reason_code_is_declared(self):
        for scenario in LEDGER_LOG.values():
            for rec in scenario["records"]:
                self.assertIn(rec["status"], p.EVENT_STATUSES)
                if rec["status"] == "rejected":
                    self.assertIn(rec["reasons"][0]["code"], p.LEDGER_REJECT_CODES, rec["reasons"])


if __name__ == "__main__":
    argv = [a for a in sys.argv if not a.startswith("--dump=")]
    dump = next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--dump=")), None)
    program = unittest.main(argv=argv, exit=False, verbosity=2)
    if dump:
        Path(dump).write_text(json.dumps(LEDGER_LOG, indent=1, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    sys.exit(0 if program.result.wasSuccessful() else 1)
