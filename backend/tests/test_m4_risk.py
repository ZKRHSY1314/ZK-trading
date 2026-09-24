"""Standalone unittest suite for ``backend/app/research/m4_risk.py`` (M4-02B) over the frozen kernel and ledger.

Run with the project interpreter (stdlib unittest; all three modules loaded by file path; no ``app`` import, no
conftest, no pytest, no SQLite, no network, no clock):

    backend/.venv/Scripts/python.exe -B -X utf8 backend/tests/test_m4_risk.py -v

All fixtures are synthetic (``SYN_*`` symbols, ``syn:`` refs, ``synthetic=True``).  Fee schedule
``HYPOTHETICAL_RISK_FEES`` (commission 0.0003 min 5.00, transfer 0.00001, sell stamp 0.0005), slippage 0.001,
tick 0.01, 100-share lots, T+1, and the risk policy parameters are arithmetic fixtures, not real tariffs or
tuned parameters.  Expected numbers are hand-calculated in the comments.  ``SCENARIO_LOG`` collects per-scenario
engine records, ledger records, snapshot and reconciliation for the runner to dump.
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

BACKEND = Path(__file__).resolve().parents[1]
KERNEL_PATH = BACKEND / "app" / "research" / "m4_execution.py"
LEDGER_PATH = BACKEND / "app" / "research" / "m4_portfolio.py"
RISK_PATH = BACKEND / "app" / "research" / "m4_risk.py"
FROZEN = {"kernel": "83a28b543b9ecc5edf8080ea39fa388f8b2bb5a8724ef68b4b532041216678c7", "ledger": "2b3eec837e4c3603661371fb94e8d942f45c9bfadbf018fc5d6ebee6fadb5360"}


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


k = _load("m4_execution_frozen_for_risk_tests", KERNEL_PATH)
lm = _load("m4_portfolio_frozen_for_risk_tests", LEDGER_PATH)
r = _load("m4_risk_under_test", RISK_PATH)

SCENARIO_LOG: dict[str, dict] = {}

A, B, BENCH = "SYN_RISK_A", "SYN_RISK_B", "SYN_INDEX_300"
SESSIONS = ("2024-03-18", "2024-03-19", "2024-03-20", "2024-03-21", "2024-03-22", "2024-03-25", "2024-03-26", "2024-03-27")
CAL = k.SessionCalendar(SESSIONS, "+08:00", "09:30", "15:00", "syn:calendar", "2024-01-01T00:00:00+08:00", True)
FEES = k.FeeSchedule("HYPOTHETICAL_RISK_FEES", "fixture-1", "hypothetical_fixture", "syn:fee-fixture", "2024-01-01", None, ("syn_main",),
                     "0.0003", "0.0003", "5.00", "0.00001", "0.0005")
ASM = k.ExecutionAssumptions("HYPOTHETICAL_RISK_ASSUMPTIONS", "hypothetical_fixture", "syn:assumption-fixture", "0.001", "1", "0.01",
                             k.LotPolicy("syn:lot_100", 100, 100, 100, "whole_odd_remainder_only", 1_000_000), k.SettlementPolicy("syn:T+1", 1))
UNIVERSE = (r.UniverseMember(A, "stock", "syn_main", "syn:listing-A"), r.UniverseMember(B, "stock", "syn_main", "syn:listing-B"))


def policy(**kw):
    base = dict(policy_id="HYPOTHETICAL_RISK_POLICY_A", provenance="hypothetical_fixture", max_position_weight="0.20", max_gross_exposure="0.60", min_cash_reserve="0",
                stop_loss_pct="0.05", profit_target_pct="0.10", max_holding_sessions=5, cooldown_sessions=2, max_mark_age_sessions=0, max_gap_pct="0.02",
                intent_expiry_sessions=1, exit_priority=("stop_loss", "profit_target", "max_holding"))
    base.update(kw)
    return r.RiskPolicy(**base)


def engine(cash="100000.00", lots=(), pol=None, engine_id="SYN-ENGINE"):
    L = lm.PortfolioLedger(k, ledger_id="SYN-RISK-LEDGER", account_ref="SYN-ACCOUNT", initial_cash=cash, initial_lots=tuple(lots))
    return r.PolicyEngine(kernel=k, ledger_module=lm, ledger=L, policy=pol or policy(), universe=UNIVERSE, benchmark_symbol=BENCH, engine_id=engine_id), L


def ctx(session, decided="16:00:00"):
    return r.DecisionContext(session, f"{session}T{decided}+08:00", CAL, FEES, ASM)


def mark(symbol, price, session, observed="15:00:00", available="15:05:00"):
    return r.Mark(symbol, price, f"{session}T{observed}+08:00", f"{session}T{available}+08:00", "syn:close-feed", True)


def signal(symbol, session, sid=None, observed="15:00:00", available="15:05:00", side="buy"):
    return r.Signal(sid or f"SIG-{symbol}-{session}", symbol, side, f"{session}T{observed}+08:00", f"{session}T{available}+08:00", "syn:rule-feed", True)


def status(symbol, st, session, observed="15:00:00", available="15:05:00"):
    return r.SecurityStatus(symbol, st, f"{session}T{observed}+08:00", f"{session}T{available}+08:00", "syn:status-feed", True)


def bench(level, session, observed="15:00:00", available="15:05:00"):
    return r.BenchmarkObservation(BENCH, level, f"{session}T{observed}+08:00", f"{session}T{available}+08:00", "syn:index-feed", True)


def evidence(symbol, session, price, *, at="09:30:00", phase="open_auction", capacity=100_000, capacity_id=None, attempt_id="A1", trad_status="tradable",
             limit_state="none", capacity_at=None, band=("30.00", "3.00")):
    t = f"{session}T{at}+08:00"
    ct = f"{session}T{capacity_at or at}+08:00"
    trad = k.TradabilityEvidence(symbol, session, trad_status, limit_state, "band", band[0], band[1], "not_st", "seasoned", f"{session}T09:15:00+08:00", f"{session}T09:15:00+08:00",
                                 "syn:tradability", True)
    px = k.PriceObservation(symbol, price, "open_auction_print" if phase == "open_auction" else "last_trade", t, t, "syn:print", "contemporaneous", True)
    cap = None if capacity is None else k.LiquidityCapacity(symbol, capacity_id or f"CAP-{symbol}-{session}-{attempt_id}", capacity, "share", "auction_matched_quantity", ct, ct,
                                                           "syn:capacity", "contemporaneous", True)
    return r.AttemptEvidence(attempt_id, t, session, phase, trad, px, cap)


def log(name, E, L):
    SCENARIO_LOG[name] = {"engine_records": list(E.records), "intents": E.intents(), "reservations": E.reservations(), "ledger_records": list(L.records),
                          "ledger_snapshot": L.snapshot(), "reconcile": L.reconcile(), "chain_hash": E.chain_hash}


class RiskCase(unittest.TestCase):
    def entry(self, rec, symbol):
        return next(e for e in rec["entries"] if e["symbol"] == symbol)

    def exit(self, rec, symbol):
        return next(e for e in rec["exits"] if e["symbol"] == symbol)


# ======================================================================================
class TestEndToEndHandCalculated(RiskCase):
    def test_decision_sizing_kernel_ledger_exit_cooldown_valuation_benchmark(self):
        E, L = engine("100000.00")
        # --- D1 (03-18 close): signal on A at 10.00; equity 100000 -> rooms 20000 / 60000 / 100000 -> budget 20000.00
        d1 = E.decide("D1", ctx("2024-03-18"), marks=(mark(A, "10.00", "2024-03-18"),), signals=(signal(A, "2024-03-18"),), benchmark=(bench("3000.00", "2024-03-18"),))
        self.assertEqual(d1["status"], "decided")
        self.assertEqual(d1["valuation"], {"complete": True, "cash": "100000.00", "gross_exposure": "0.00", "equity": "100000.00", "gross_weight": "0.000000", "positions": {}, "incomplete_symbols": []})
        e = self.entry(d1, A)
        # reserved price ceil_tick(10.00 x 1.001) = 10.01; floor(20000 / 10.01) = 1998 -> 1900 lots; est 1900 x 10.01 = 19019.00 + max(5.7057->5.71, 5.00) + 0.19 = 19024.90
        self.assertEqual((e["decision"], e["quantity"], e["limit_price"], e["estimated_cost"], e["reserved_budget"]), ("buy", 1900, "10.20", "19024.90", "20000.00"))
        self.assertEqual(e["rooms"], {"position_room": "20000.00", "portfolio_room": "60000.00", "cash_room": "100000.00", "budget": "20000.00", "reserved_price": "10.01", "mark": "10.00"})
        self.assertEqual(d1["benchmark"]["level"], "3000.00")
        self.assertEqual(E.reservations()["reserved_cash"], "20000.00")
        # --- X1 (03-19 open): observed 10.05 -> kernel fill 10.07; re-check 1900 x 10.07 = 19133.00 + 5.74 + 0.19 = 19138.93 <= 20000 -> full 1900
        x1 = E.execute("D1:buy:SYN_RISK_A", ctx("2024-03-18"), evidence(A, "2024-03-19", "10.05"))
        self.assertEqual(x1["status"], "filled")
        o = x1["outcome"]
        self.assertEqual((o["filled_quantity"], o["fill_price"], o["fees"], o["cash_after"], o["gap"]), (1900, "10.07", {"commission": "5.74", "transfer_fee": "0.19", "stamp_duty": "0.00", "total": "5.93"}, "80861.07", None))
        self.assertEqual(E.reservations()["reserved_cash"], "0.00")
        self.assertEqual(L.positions(), {A: 1900})
        # --- D2 (03-19 close): mark 10.30 -> value 19570.00, equity 100431.07, weight 0.194860; entry ref 19138.93 / 1900 = 10.0731 -> hold
        d2 = E.decide("D2", ctx("2024-03-19"), marks=(mark(A, "10.30", "2024-03-19"),), benchmark=(bench("3030.00", "2024-03-19"),))
        v = d2["valuation"]
        self.assertEqual((v["complete"], v["cash"], v["gross_exposure"], v["equity"], v["gross_weight"]), (True, "80861.07", "19570.00", "100431.07", "0.194860"))
        self.assertEqual(v["positions"][A]["entry_cost_reference"], "10.0731")
        self.assertEqual(v["positions"][A]["weight"], "0.194860")
        self.assertEqual(self.exit(d2, A)["decision"], "hold")
        # --- D3 (03-20 close): mark 9.50 <= 10.0731 x 0.95 = 9.5695 -> stop_loss -> sell 1900, limit floor_tick(9.50 x 0.98 = 9.31) = 9.31
        d3 = E.decide("D3", ctx("2024-03-20"), marks=(mark(A, "9.50", "2024-03-20"),), benchmark=(bench("2990.00", "2024-03-20"),))
        x = self.exit(d3, A)
        self.assertEqual((x["decision"], x["reason"], x["quantity"], x["limit_price"]), ("exit", "stop_loss", 1900, "9.31"))
        self.assertEqual(x["checks"], {"stop_loss": True, "profit_target": False, "max_holding": False})
        # --- X2 (03-21 open): observed 9.40 -> fill floor_tick(9.40 x 0.999 = 9.3906) = 9.39; gross 17841.00; fees 5.35 + 0.18 + 8.92 = 14.45; proceeds 17826.55
        x2 = E.execute("D3:sell:SYN_RISK_A", ctx("2024-03-20"), evidence(A, "2024-03-21", "9.40", attempt_id="A2"))
        self.assertEqual(x2["status"], "filled")
        o2 = x2["outcome"]
        self.assertEqual((o2["fill_price"], o2["fees"]["total"], o2["cash_after"], o2["cooldown_started_session"]), ("9.39", "14.45", "98687.62", "2024-03-21"))
        self.assertEqual(L.snapshot()["realized_pnl_total"], "-1312.38")          # 17826.55 - 19138.93
        self.assertEqual(L.positions(), {})
        # --- cooldown: D4 (03-21) 0 of 2, D5 (03-22) 1 of 2 refused; D6 (03-25) exactly 2 -> allowed and sized on the new equity
        d4 = E.decide("D4", ctx("2024-03-21"), marks=(mark(A, "9.60", "2024-03-21"),), signals=(signal(A, "2024-03-21"),), benchmark=(bench("2960.00", "2024-03-21"),))
        self.assertEqual((self.entry(d4, A)["decision"], self.entry(d4, A)["reason"]), ("refused", "cooldown_active"))
        d5 = E.decide("D5", ctx("2024-03-22"), marks=(mark(A, "9.70", "2024-03-22"),), signals=(signal(A, "2024-03-22"),))
        self.assertEqual(self.entry(d5, A)["reason"], "cooldown_active")
        d6 = E.decide("D6", ctx("2024-03-25"), marks=(mark(A, "9.80", "2024-03-25"),), signals=(signal(A, "2024-03-25"),))
        e6 = self.entry(d6, A)
        # equity 98687.62 -> position room 19737.524 -> budget 19737.52; reserved price ceil(9.80 x 1.001 = 9.8098) = 9.81; floor(19737.52 / 9.81) = 2011 -> 2000
        # estimate 2000 x 9.81 = 19620.00 + max(5.886 -> 5.89, 5.00) + 0.20 = 19626.09 <= 19737.52
        self.assertEqual((e6["decision"], e6["quantity"], e6["estimated_cost"], e6["reserved_budget"], e6["limit_price"]), ("buy", 2000, "19626.09", "19737.52", "10.00"))
        # --- performance at 03-21 close vs benchmark 03-18 -> 03-21: equity 98687.62 -> -0.013124; index 2960 / 3000 - 1 = -0.013333
        perf = E.performance(ctx("2024-03-21"), marks=(mark(A, "9.60", "2024-03-21"),), benchmark=(bench("3000.00", "2024-03-18"), bench("2960.00", "2024-03-21")),
                             start_session="2024-03-18", initial_cash="100000.00")
        self.assertEqual((perf["complete"], perf["equity"], perf["return"], perf["realized_pnl_total"]), (True, "98687.62", "-0.013124", "-1312.38"))
        self.assertEqual((perf["benchmark"]["status"], perf["benchmark"]["return"]), ("observed", "-0.013333"))
        self.assertTrue(perf["review_only"] and not perf["live_trading_enabled"] and not perf["training_eligible"] and not perf["M4_complete"])
        self.assertTrue(L.reconcile()["ok"])
        log("e2e.hand_calculated", E, L)


# ======================================================================================
class TestCausalValuation(RiskCase):
    def test_future_or_stale_or_missing_marks_make_valuation_incomplete_and_block_buys(self):
        E, L = engine("100000.00", lots=(lm.InitialLot(A, 1000, "2024-03-15", "10000.00", "syn:opening"),))
        # future availability (mark available after decided_at) -> refused, valuation incomplete, held position kept
        d = E.decide("D1", ctx("2024-03-18"), marks=(mark(A, "10.00", "2024-03-18", available="16:30:00"),), signals=(signal(B, "2024-03-18"), ), benchmark=())
        self.assertEqual(d["refusals"][0]["code"], "future_evidence")
        v = d["valuation"]
        self.assertEqual((v["complete"], v["incomplete_symbols"], v["equity"], v["positions"][A]["quantity"], v["positions"][A]["value"]), (False, [A], None, 1000, None))
        self.assertEqual(v["positions"][A]["unresolved_reason"]["code"], "missing_mark")
        self.assertEqual((self.entry(d, B)["decision"], self.entry(d, B)["reason"]), ("refused", "valuation_incomplete"))
        self.assertEqual(self.exit(d, A)["decision"], "unresolved")
        # stale mark (age 1 > max 0)
        d2 = E.decide("D2", ctx("2024-03-19"), marks=(mark(A, "10.00", "2024-03-18"),), signals=(signal(B, "2024-03-19"),))
        self.assertEqual(d2["valuation"]["positions"][A]["unresolved_reason"]["code"], "stale_mark")
        self.assertEqual(self.entry(d2, B)["reason"], "valuation_incomplete")
        # conflicting marks at the same instant are inconsistent evidence, not a silent pick
        d4 = E.decide("D4", ctx("2024-03-20"), marks=(mark(A, "10.00", "2024-03-20"), mark(A, "10.50", "2024-03-20")))
        self.assertEqual(d4["valuation"]["positions"][A]["unresolved_reason"]["code"], "inconsistent_evidence")
        # a mark observed after the decision instant is future evidence even if the timestamp lies on the decision session
        d5 = E.decide("D5", ctx("2024-03-21"), marks=(mark(A, "10.00", "2024-03-21", observed="16:30:00", available="16:30:00"),))
        self.assertEqual((d5["refusals"][0]["code"], d5["valuation"]["complete"]), ("future_evidence", False))
        # a policy allowing age 1 accepts the same mark
        E3, _ = engine("100000.00", lots=(lm.InitialLot(A, 1000, "2024-03-15", "10000.00", "syn:opening"),), pol=policy(max_mark_age_sessions=1))
        d3 = E3.decide("D1", ctx("2024-03-19"), marks=(mark(A, "10.00", "2024-03-18"),))
        self.assertTrue(d3["valuation"]["complete"])
        self.assertEqual(d3["valuation"]["equity"], "110000.00")
        self.assertEqual(L.positions(), {A: 1000})
        log("valuation.incomplete", E, L)

    def test_decision_before_close_or_out_of_order_is_refused(self):
        E, L = engine()
        early = E.decide("D1", ctx("2024-03-18", decided="14:00:00"), marks=(mark(A, "10.00", "2024-03-18", observed="13:00:00", available="13:00:00"),))
        self.assertEqual((early["status"], early["refusals"][0]["code"]), ("refused", "inconsistent_evidence"))
        ok = E.decide("D2", ctx("2024-03-19"), marks=(mark(A, "10.00", "2024-03-19"),))
        self.assertEqual(ok["status"], "decided")
        back = E.decide("D3", ctx("2024-03-18"), marks=(mark(A, "10.00", "2024-03-18"),))
        self.assertEqual((back["status"], back["refusals"][0]["code"], back["refusals"][0]["policy_event_clock"]), ("refused", "chronology_violation", "2024-03-19T16:00:00+08:00"))
        dup = E.decide("D2", ctx("2024-03-20"), marks=(mark(A, "10.00", "2024-03-20"),))
        self.assertEqual(dup["refusals"][0]["code"], "duplicate_signal")


# ======================================================================================
class TestSizingAndReservations(RiskCase):
    def test_exact_exposure_boundary_and_zero_size(self):
        # cash 10000: position room 2000.00; reserved price 10.01 -> floor(2000 / 10.01) = 199 -> 100 lots; est 1001.00 + 5.00 + 0.01 = 1006.01 <= 2000
        E, L = engine("10000.00")
        d = E.decide("D1", ctx("2024-03-18"), marks=(mark(A, "10.00", "2024-03-18"),), signals=(signal(A, "2024-03-18"),))
        self.assertEqual((self.entry(d, A)["quantity"], self.entry(d, A)["estimated_cost"]), (100, "1006.01"))
        # cash 5000: position room 1000.00 < one lot 1006.01 -> zero size, never a forced lot
        E2, _ = engine("5000.00")
        d2 = E2.decide("D1", ctx("2024-03-18"), marks=(mark(A, "10.00", "2024-03-18"),), signals=(signal(A, "2024-03-18"),))
        z = self.entry(d2, A)
        self.assertEqual((z["decision"], z["reason"], z["estimated_cost_one_lot"], z["rooms"]["budget"]), ("zero_size", "insufficient_cash_or_room", "1006.01", "1000.00"))
        self.assertEqual(E2.intents(), {})
        # exact boundary: budget 1006.01 fits one lot; 1006.00 does not (cash 5030.05 -> room 1006.01; cash 5030.00 -> room 1006.00)
        E3, _ = engine("5030.05")
        self.assertEqual(self.entry(E3.decide("D1", ctx("2024-03-18"), marks=(mark(A, "10.00", "2024-03-18"),), signals=(signal(A, "2024-03-18"),)), A)["quantity"], 100)
        E4, _ = engine("5030.00")
        self.assertEqual(self.entry(E4.decide("D1", ctx("2024-03-18"), marks=(mark(A, "10.00", "2024-03-18"),), signals=(signal(A, "2024-03-18"),)), A)["decision"], "zero_size")

    def test_simultaneous_signals_share_cash_and_exposure_sequentially(self):
        # gross exposure cap 0.60 x 100000 = 60000 with position cap 20000 each: A and B both get 20000 budgets; a third symbol would be capped by cash/exposure
        E, L = engine("100000.00", pol=policy(max_position_weight="0.50", max_gross_exposure="0.60"))
        d = E.decide("D1", ctx("2024-03-18"), marks=(mark(A, "10.00", "2024-03-18"), mark(B, "20.00", "2024-03-18")), signals=(signal(B, "2024-03-18"), signal(A, "2024-03-18")))
        ea, eb = self.entry(d, A), self.entry(d, B)
        self.assertEqual([x["symbol"] for x in d["entries"]], [A, B])                 # stable (symbol, signal_id) order regardless of input order
        self.assertEqual((ea["reserved_budget"], ea["rooms"]["portfolio_room"]), ("50000.00", "60000.00"))
        self.assertEqual((eb["reserved_budget"], eb["rooms"]["portfolio_room"], eb["rooms"]["cash_room"]), ("10000.00", "10000.00", "50000.00"))   # 60000 - 50000 reserved
        self.assertEqual(d["reservations_after"], {"reserved_cash": "60000.00", "reserved_exposure": "60000.00"})
        # B: reserved price ceil(20.00 x 1.001 = 20.02) = 20.02; floor(10000 / 20.02) = 499 -> 400; est 8008.00 + 5.00 + 0.08 = 8013.08
        self.assertEqual((eb["quantity"], eb["estimated_cost"]), (400, "8013.08"))
        # the next decision (16:00, after the one-session window closed at 15:00) expires both intents deterministically and releases their reservations
        d2 = E.decide("D2", ctx("2024-03-19"), marks=(mark(A, "10.00", "2024-03-19"), mark(B, "20.00", "2024-03-19")), signals=(signal(A, "2024-03-19"),))
        self.assertEqual([x["intent_id"] for x in d2["expired_intents"]], ["D1:buy:SYN_RISK_A", "D1:buy:SYN_RISK_B"])
        self.assertEqual(d2["expired_intents"][0]["released_remaining"], "50000.00")
        self.assertEqual((self.entry(d2, A)["decision"], E.reservations()["reserved_cash"]), ("buy", "50000.00"))
        # with a two-session window the intents are still live at the next decision and block re-sizing of the same symbols
        E2, _ = engine("100000.00", pol=policy(max_position_weight="0.50", max_gross_exposure="0.60", intent_expiry_sessions=2))
        E2.decide("D1", ctx("2024-03-18"), marks=(mark(A, "10.00", "2024-03-18"), mark(B, "20.00", "2024-03-18")), signals=(signal(B, "2024-03-18"), signal(A, "2024-03-18")))
        d3 = E2.decide("D2", ctx("2024-03-19"), marks=(mark(A, "10.00", "2024-03-19"), mark(B, "20.00", "2024-03-19")), signals=(signal(A, "2024-03-19"),))
        self.assertEqual((self.entry(d3, A)["reason"], d3["expired_intents"]), ("symbol_pending_intent", []))
        log("sizing.shared_reservations", E, L)

    def test_execution_gap_recheck_downsizes_or_cancels_without_a_later_close(self):
        E, L = engine("10000.00", pol=policy(max_position_weight="0.30"))           # position room 3000.00 -> 200 shares at 10.01 (est 2002 + 5 + 0.02 = 2007.02)
        d = E.decide("D1", ctx("2024-03-18"), marks=(mark(A, "10.00", "2024-03-18"),), signals=(signal(A, "2024-03-18"),))
        self.assertEqual(self.entry(d, A)["quantity"], 200)
        # gap up to 14.90 (fill 14.92): 200 x 14.92 = 2984.00 + 5.00 + 0.03 = 2989.03 <= 3000 -> still 200; at 14.99 (fill 15.01): 3002.00 > 3000 -> 100
        x = E.execute("D1:buy:SYN_RISK_A", ctx("2024-03-18"), evidence(A, "2024-03-19", "14.99"))
        self.assertEqual(x["status"], "expired")                                     # 15.01 > limit 10.20 -> kernel leaves it unfilled; the only auction of a 1-session intent is used
        self.assertEqual(E.reservations()["reserved_cash"], "0.00")
        gap = x["outcome"]["gap"]
        self.assertEqual((gap["code"], gap["from"], gap["to"]), ("gap_downsized", 200, 100))
        self.assertEqual((gap["recheck"]["observed_price"], gap["recheck"]["fill_price_estimate"], gap["recheck"]["estimated_cost"], gap["recheck"]["reservation_remaining"], gap["recheck"]["permissible"]),
                         ("14.99", "15.01", "1506.02", "3000.00", "3000.00"))
        self.assertEqual(x["outcome"]["reasons"][0]["kernel_reasons"][0]["code"], "fill_price_exceeds_limit_price")
        # beyond the whole budget: cancelled, reservation released, nothing posted
        E2, L2 = engine("10000.00", pol=policy(max_position_weight="0.30", max_gap_pct="0.5"))
        E2.decide("D1", ctx("2024-03-18"), marks=(mark(A, "10.00", "2024-03-18"),), signals=(signal(A, "2024-03-18"),))
        x2 = E2.execute("D1:buy:SYN_RISK_A", ctx("2024-03-18"), evidence(A, "2024-03-19", "29.99"))    # fill 30.02 -> one lot 3002.00 + 5 + 0.03 > 3000
        self.assertEqual((x2["status"], x2["reason"], x2["recheck"]["affordable_quantity"]), ("cancelled", "gap_exceeds_budget", 0))
        self.assertEqual(E2.reservations()["reserved_cash"], "0.00")
        self.assertEqual(L2.snapshot()["cash"], "10000.00")
        # a moderate gap within the limit fills the re-checked size through the kernel
        E3, L3 = engine("10000.00", pol=policy(max_position_weight="0.30", max_gap_pct="0.5"))
        E3.decide("D1", ctx("2024-03-18"), marks=(mark(A, "10.00", "2024-03-18"),), signals=(signal(A, "2024-03-18"),))
        # observed 14.97 -> fill ceil(14.97 x 1.001 = 14.98497) = 14.99 <= limit 15.00; 200 x 14.99 = 2998.00 + 5.00 + 0.03 = 3003.03 > 3000 -> 100 (1499.00 + 5.00 + 0.01 = 1504.01)
        x3 = E3.execute("D1:buy:SYN_RISK_A", ctx("2024-03-18"), evidence(A, "2024-03-19", "14.97"))
        self.assertEqual((x3["status"], x3["outcome"]["filled_quantity"], x3["outcome"]["fill_price"], x3["outcome"]["cash_after"]), ("filled", 100, "14.99", "8495.99"))
        self.assertEqual(x3["outcome"]["gap"]["to"], 100)
        self.assertEqual(E3.intents()["D1:buy:SYN_RISK_A"]["quantity"], 100)
        self.assertEqual(L3.positions(), {A: 100})
        log("sizing.gap_recheck", E3, L3)

    def test_partial_fill_keeps_the_reservation_and_expired_or_rejected_release_it(self):
        E, L = engine("100000.00", pol=policy(entry_phase="continuous"))
        E.decide("D1", ctx("2024-03-18"), marks=(mark(A, "10.00", "2024-03-18"),), signals=(signal(A, "2024-03-18"),))
        part = E.execute("D1:buy:SYN_RISK_A", ctx("2024-03-18"), evidence(A, "2024-03-19", "10.00", at="10:00:00", phase="continuous", capacity=1000, capacity_id="CAP-P"))
        self.assertEqual((part["status"], part["outcome"]["filled_quantity"]), ("partially_filled", 1000))
        self.assertEqual(E.intents()["D1:buy:SYN_RISK_A"]["remaining"], 900)
        # 1000 x 10.01 = 10010.00 + max(3.003 -> 3.00, 5.00) + 0.10 = 10015.10 debited from the 20000.00 reservation -> 9984.90 remaining
        self.assertEqual(E.reservations()["by_intent"]["D1:buy:SYN_RISK_A"], {"symbol": A, "original_budget": "20000.00", "consumed": "10015.10", "remaining": "9984.90", "kind": "buy_cash_and_exposure"})
        self.assertEqual(E.reservations()["reserved_cash"], "9984.90")
        rest = E.execute("D1:buy:SYN_RISK_A", ctx("2024-03-18"), evidence(A, "2024-03-19", "10.00", at="11:00:00", phase="continuous", capacity=5000, capacity_id="CAP-Q", attempt_id="A2"))
        self.assertEqual((rest["status"], rest["outcome"]["filled_quantity"]), ("filled", 900))   # 900 x 10.01 = 9009.00 + 5.00 + 0.09 = 9014.09 <= 9984.90
        self.assertEqual(E.reservations()["reserved_cash"], "0.00")
        self.assertEqual(L.positions(), {A: 1900})
        # an intent unfilled on its final session expires and releases; a kernel-rejected attempt leaves the intent and reservation untouched
        E2, L2 = engine("100000.00")
        E2.decide("D1", ctx("2024-03-18"), marks=(mark(B, "20.00", "2024-03-18"),), signals=(signal(B, "2024-03-18"),))
        susp = E2.execute("D1:buy:SYN_RISK_B", ctx("2024-03-18"), evidence(B, "2024-03-19", "20.00", trad_status="suspended"))
        self.assertEqual(susp["status"], "expired")                                    # one-session open-auction intent, suspended at its only opportunity
        self.assertEqual(E2.reservations()["reserved_cash"], "0.00")
        E3, L3 = engine("100000.00")
        E3.decide("D1", ctx("2024-03-18"), marks=(mark(B, "20.00", "2024-03-18"),), signals=(signal(B, "2024-03-18"),))
        bad = E3.execute("D1:buy:SYN_RISK_B", ctx("2024-03-18"), evidence(B, "2024-03-19", "20.00", at="09:30:00", phase="continuous"))   # undeclared phase -> refused before the kernel
        self.assertEqual((bad["status"], bad["reason"], E3.intents()["D1:buy:SYN_RISK_B"]["status"]), ("refused", "phase_mismatch", "pending"))
        self.assertEqual(E3.reservations()["reserved_cash"], "20000.00")
        log("sizing.partial_and_release", E, L)


# ======================================================================================
class TestExitsAndCooldown(RiskCase):
    def held(self, cash="100000.00", entry_session="2024-03-18", cost="10073.12", quantity=1000, pol=None):
        return engine(cash, lots=(lm.InitialLot(A, quantity, entry_session, cost, "syn:opening"),), pol=pol)

    def test_touch_is_not_a_fill_and_stop_executes_at_the_next_open_print(self):
        E, L = self.held()                                                             # ref 10.0731 -> stop 9.5695
        d = E.decide("D1", ctx("2024-03-19"), marks=(mark(A, "9.60", "2024-03-19"),))   # close above the threshold: an intrabar touch is not consulted
        self.assertEqual(self.exit(d, A)["decision"], "hold")
        d2 = E.decide("D2", ctx("2024-03-20"), marks=(mark(A, "9.56", "2024-03-20"),))  # close at/below threshold -> stop
        self.assertEqual((self.exit(d2, A)["decision"], self.exit(d2, A)["reason"], self.exit(d2, A)["limit_price"]), ("exit", "stop_loss", "9.36"))   # floor(9.56 x 0.98 = 9.3688)
        # gap-down open 9.30 (fill 9.29 < limit 9.36): the kernel leaves it unfilled; the position is NOT closed and no cooldown starts
        x = E.execute("D2:sell:SYN_RISK_A", ctx("2024-03-20"), evidence(A, "2024-03-21", "9.30"))
        self.assertEqual((x["status"], L.positions(), E.records[-1]["state_summary"]["exit_sessions"]), ("expired", {A: 1000}, {}))
        self.assertEqual(x["outcome"]["reasons"][0]["kernel_reasons"][0]["code"], "fill_price_below_limit_price")
        # the next decision re-evaluates and issues a fresh exit intent; the open print then fills at the legally observed price
        d3 = E.decide("D3", ctx("2024-03-21"), marks=(mark(A, "9.30", "2024-03-21"),))
        self.assertEqual(self.exit(d3, A)["decision"], "exit")
        x2 = E.execute("D3:sell:SYN_RISK_A", ctx("2024-03-21"), evidence(A, "2024-03-22", "9.35", attempt_id="A2"))
        self.assertEqual((x2["status"], x2["outcome"]["fill_price"], x2["outcome"]["cooldown_started_session"]), ("filled", "9.34", "2024-03-22"))   # floor(9.35 x 0.999 = 9.34065)
        self.assertEqual(L.positions(), {})
        log("exits.stop_next_open", E, L)

    def test_exit_priority_target_and_max_holding(self):
        E, _ = self.held(pol=policy(exit_priority=("profit_target", "stop_loss", "max_holding")))
        d = E.decide("D1", ctx("2024-03-19"), marks=(mark(A, "11.09", "2024-03-19"),))     # 11.09 >= 10.0731 x 1.10 = 11.0804 -> target
        self.assertEqual(self.exit(d, A)["reason"], "profit_target")
        # an entry session outside the injected calendar cannot be aged: sessions_held is None and max_holding never fires (documented limitation)
        E2, _ = self.held(entry_session="2024-03-15", pol=policy(max_holding_sessions=1))
        d2 = E2.decide("D1", ctx("2024-03-20"), marks=(mark(A, "10.10", "2024-03-20"),))
        self.assertIsNone(d2["valuation"]["positions"][A]["sessions_held"])
        self.assertEqual(self.exit(d2, A)["decision"], "hold")
        # entry 03-18: held 2 sessions at 03-20 (hold), 3 at 03-21 (max_holding)
        E3, _ = self.held(entry_session="2024-03-18", pol=policy(max_holding_sessions=3))
        self.assertEqual(self.exit(E3.decide("D1", ctx("2024-03-20"), marks=(mark(A, "10.10", "2024-03-20"),)), A)["decision"], "hold")
        self.assertEqual(self.exit(E3.decide("D2", ctx("2024-03-21"), marks=(mark(A, "10.10", "2024-03-21"),)), A)["reason"], "max_holding")
        # coincidence: stop and max_holding both true -> policy order decides
        E4, _ = self.held(entry_session="2024-03-18", pol=policy(max_holding_sessions=3, exit_priority=("max_holding", "stop_loss", "profit_target")))
        d4 = E4.decide("D1", ctx("2024-03-21"), marks=(mark(A, "9.00", "2024-03-21"),))
        self.assertEqual((self.exit(d4, A)["reason"], self.exit(d4, A)["checks"]), ("max_holding", {"stop_loss": True, "profit_target": False, "max_holding": True}))

    def test_partial_exit_keeps_residual_and_cooldown_only_on_full_close(self):
        E, L = self.held(pol=policy(exit_phase="continuous"))
        E.decide("D1", ctx("2024-03-19"), marks=(mark(A, "9.00", "2024-03-19"),))
        part = E.execute("D1:sell:SYN_RISK_A", ctx("2024-03-19"), evidence(A, "2024-03-20", "9.00", at="10:00:00", phase="continuous", capacity=600, capacity_id="CAP-X"))
        self.assertEqual((part["status"], part["outcome"]["filled_quantity"], L.positions()), ("partially_filled", 600, {A: 400}))
        self.assertNotIn("cooldown_started_session", part["outcome"])
        self.assertEqual(E.records[-1]["state_summary"]["exit_sessions"], {})
        dup = E.execute("D1:sell:SYN_RISK_A", ctx("2024-03-19"), evidence(A, "2024-03-20", "9.00", at="10:00:00", phase="continuous", capacity=600, capacity_id="CAP-X"))
        self.assertEqual(dup["status"], "duplicate")                                  # replay: no ledger call, no second sale, no cooldown
        self.assertEqual(L.positions(), {A: 400})
        rest = E.execute("D1:sell:SYN_RISK_A", ctx("2024-03-19"), evidence(A, "2024-03-20", "9.00", at="11:00:00", phase="continuous", capacity=5000, capacity_id="CAP-Y", attempt_id="A2"))
        self.assertEqual((rest["status"], rest["outcome"]["cooldown_started_session"], L.positions()), ("filled", "2024-03-20", {}))
        # cooldown 2 sessions from 03-20: 03-20 (0) and 03-21 (1) refused, 03-22 (2) allowed; a non-trading weekend does not count
        self.assertEqual(self.entry(E.decide("D2", ctx("2024-03-20"), marks=(mark(A, "9.00", "2024-03-20"),), signals=(signal(A, "2024-03-20"),)), A)["reason"], "cooldown_active")
        self.assertEqual(self.entry(E.decide("D3", ctx("2024-03-21"), marks=(mark(A, "9.00", "2024-03-21"),), signals=(signal(A, "2024-03-21"),)), A)["reason"], "cooldown_active")
        self.assertEqual(self.entry(E.decide("D4", ctx("2024-03-22"), marks=(mark(A, "9.00", "2024-03-22"),), signals=(signal(A, "2024-03-22"),)), A)["decision"], "buy")
        # a still-live (two-session) partial exit intent is reported as exit_pending at the next decision and blocks a buy of the symbol
        E2, L2 = self.held(pol=policy(exit_phase="continuous", intent_expiry_sessions=2))
        E2.decide("D1", ctx("2024-03-19"), marks=(mark(A, "9.00", "2024-03-19"),))
        E2.execute("D1:sell:SYN_RISK_A", ctx("2024-03-19"), evidence(A, "2024-03-20", "9.00", at="10:00:00", phase="continuous", capacity=600, capacity_id="CAP-X"))
        d2 = E2.decide("D2", ctx("2024-03-20"), marks=(mark(A, "9.00", "2024-03-20"),), signals=(signal(A, "2024-03-20"),))
        self.assertEqual((self.exit(d2, A)["decision"], self.entry(d2, A)["reason"], d2["expired_intents"]), ("exit_pending", "symbol_held", []))
        log("exits.partial_and_cooldown", E, L)

    def test_suspension_and_limit_down_leave_the_exit_pending_or_expired_without_closing(self):
        E, L = self.held()
        E.decide("D1", ctx("2024-03-19"), marks=(mark(A, "9.00", "2024-03-19"),))
        s = E.execute("D1:sell:SYN_RISK_A", ctx("2024-03-19"), evidence(A, "2024-03-20", "9.00", trad_status="suspended"))
        self.assertEqual((s["status"], s["outcome"]["kernel_status"], L.positions()), ("expired", "unfilled", {A: 1000}))
        E2, L2 = self.held(pol=policy(intent_expiry_sessions=2))
        E2.decide("D1", ctx("2024-03-19"), marks=(mark(A, "9.00", "2024-03-19"),))
        ld = E2.execute("D1:sell:SYN_RISK_A", ctx("2024-03-19"), evidence(A, "2024-03-20", "9.00", limit_state="limit_down"))
        self.assertEqual((ld["status"], L2.positions()), ("unfilled_live", {A: 1000}))
        self.assertEqual(E2.records[-1]["state_summary"]["exit_sessions"], {})


# ======================================================================================
class TestBenchmarkAndDelisting(RiskCase):
    def test_benchmark_missing_is_not_zero_and_future_levels_are_refused(self):
        E, _ = engine()
        obs = (bench("3000.00", "2024-03-18"), bench("2960.00", "2024-03-21"), bench("3100.00", "2024-03-22", available="16:30:00"))
        ok = E.benchmark_return("2024-03-18", "2024-03-21", obs, "2024-03-21T16:00:00+08:00", CAL)
        self.assertEqual((ok["status"], ok["return"]), ("observed", "-0.013333"))
        missing = E.benchmark_return("2024-03-18", "2024-03-20", obs, "2024-03-20T16:00:00+08:00", CAL)
        self.assertEqual((missing["status"], missing["return"], missing["levels"]), ("missing", None, {"2024-03-18": "3000.00", "2024-03-20": None}))
        future = E.benchmark_return("2024-03-18", "2024-03-22", obs, "2024-03-22T16:00:00+08:00", CAL)
        self.assertEqual((future["status"], future["refusals"][0]["code"]), ("missing", "future_evidence"))
        d = E.decide("D1", ctx("2024-03-19"), marks=(mark(A, "10.00", "2024-03-19"),), signals=(signal(BENCH, "2024-03-19"),), benchmark=obs)
        self.assertEqual((self.entry(d, BENCH)["reason"], d["benchmark"]["status"]), ("benchmark_symbol", "missing"))
        with self.assertRaises(r.RiskInputError):
            r.PolicyEngine(kernel=k, ledger_module=lm, ledger=engine()[1], policy=policy(), universe=UNIVERSE + (r.UniverseMember(BENCH, "stock", "x", "y"),), benchmark_symbol=BENCH, engine_id="X")

    def test_future_delisting_announcement_versus_known_delisting_with_unresolved_holding(self):
        E, L = engine("100000.00", lots=(lm.InitialLot(A, 1000, "2024-03-18", "10073.12", "syn:opening"),))
        announced_later = status(A, "delisting_announced", "2024-03-19", available="16:30:00")      # not yet available at 16:00
        d = E.decide("D1", ctx("2024-03-19"), marks=(mark(A, "10.00", "2024-03-19"), mark(B, "20.00", "2024-03-19")), signals=(signal(A, "2024-03-19", sid="S-A"), signal(B, "2024-03-19")),
                     statuses=(announced_later,))
        self.assertEqual(d["refusals"][0]["code"], "future_evidence")
        self.assertEqual(d["valuation"]["positions"][A]["status"], "listed")
        self.assertEqual(self.entry(d, A)["reason"], "symbol_held")
        self.assertEqual(self.entry(d, B)["decision"], "buy")
        # once available: no new buy of A; the holding is kept and still valued while listed/announced
        cancelled = E.cancel("D1:buy:SYN_RISK_B", "fixture cleanup")
        self.assertEqual((cancelled["status"], cancelled["released_reservation"], E.reservations()["reserved_cash"]), ("cancelled", "22000.00", "0.00"))   # equity 100000 + 1000 x 10.00 -> position room 22000
        d2 = E.decide("D2", ctx("2024-03-20"), marks=(mark(A, "10.00", "2024-03-20"), mark(B, "20.00", "2024-03-20")), signals=(signal(B, "2024-03-20"),),
                      statuses=(announced_later, status(B, "delisting_announced", "2024-03-20")))
        self.assertEqual(self.entry(d2, B)["reason"], "security_not_tradable")
        self.assertEqual((d2["valuation"]["complete"], d2["valuation"]["positions"][A]["status"]), (True, "delisting_announced"))
        # delisted: unresolved holding, incomplete valuation/performance, no liquidation posted; hypothetical scenario separate;
        # the terminal status cannot rewrite the earlier decision records or membership
        earlier = [x["record_hash"] for x in E.records]
        delisted = status(A, "delisted", "2024-03-21")
        d3 = E.decide("D3", ctx("2024-03-21"), marks=(mark(A, "10.00", "2024-03-21"),), statuses=(announced_later, delisted))
        self.assertEqual([x["record_hash"] for x in E.records[: len(earlier)]], earlier)
        self.assertIn(A, E.universe)
        self.assertEqual((d3["valuation"]["complete"], d3["valuation"]["incomplete_symbols"], self.exit(d3, A)["decision"]), (False, [A], "unresolved"))
        perf = E.performance(ctx("2024-03-21"), marks=(mark(A, "10.00", "2024-03-21"),), statuses=(delisted,), start_session="2024-03-18", initial_cash="100000.00",
                             hypothetical_terminal_marks=(r.Mark(A, "0.00", "2024-03-21T15:00:00+08:00", "2024-03-21T15:00:00+08:00", "syn:HYPOTHETICAL-terminal-zero", True),))
        self.assertEqual((perf["complete"], perf["equity"], perf["return"], perf["unresolved_positions"]), (False, None, None, [A]))
        self.assertIn("no liquidation cash is posted", perf["positions"][A]["limitation"])
        self.assertEqual(perf["hypothetical_terminal_scenario"]["hypothetical_equity"], "100000.00")
        self.assertEqual(perf["hypothetical_terminal_scenario"]["ledger_cash_unchanged"], "100000.00")
        self.assertEqual(L.positions(), {A: 1000})
        self.assertEqual(L.snapshot()["cash"], "100000.00")
        self.assertTrue(L.reconcile()["ok"])
        log("delisting.unresolved", E, L)


# ======================================================================================
class TestCodexReview01CumulativeBudget(RiskCase):
    """P1-1: every applied fill debits its actual cost from the SAME reservation; a current-risk re-check precedes each application."""

    def half(self, cash="10000.00", **kw):
        base = dict(max_position_weight="0.50", max_gross_exposure="0.50", entry_phase="continuous", max_gap_pct="0.5")
        base.update(kw)
        return engine(cash, pol=policy(**base))

    def intent(self, E):
        d = E.decide("D1", ctx("2024-03-18"), marks=(mark(A, "10.00", "2024-03-18"),), signals=(signal(A, "2024-03-18"),))
        e = self.entry(d, A)
        # cash 10000 -> budget 5000.00; reserved price 10.01; floor(5000 / 10.01) = 499 -> 400; est 4004.00 + 5.00 + 0.04 = 4009.04
        self.assertEqual((e["quantity"], e["reserved_budget"], e["estimated_cost"]), (400, "5000.00", "4009.04"))
        return "D1:buy:SYN_RISK_A"

    def att(self, price, at, capacity, attempt_id, band=("30.00", "3.00")):
        return evidence(A, "2024-03-19", price, at=at, phase="continuous", capacity=capacity, capacity_id=f"CAP-{attempt_id}", attempt_id=attempt_id, band=band)

    def test_different_price_partial_fills_never_exceed_the_reservation_or_current_limits(self):
        E, L = self.half()
        iid = self.intent(E)
        x1 = E.execute(iid, ctx("2024-03-18"), self.att("10.00", "10:00:00", 100, "A1"))
        # fill 100 @ 10.01: cost 1001.00 + 5.00 + 0.01 = 1006.01 -> consumed 1006.01, remaining 3993.99; cash 8993.99
        self.assertEqual((x1["status"], x1["outcome"]["filled_quantity"], x1["outcome"]["cash_after"]), ("partially_filled", 100, "8993.99"))
        self.assertEqual(x1["outcome"]["reservation"], {"symbol": A, "original_budget": "5000.00", "consumed": "1006.01", "remaining": "3993.99", "kind": "buy_cash_and_exposure"})
        x2 = E.execute(iid, ctx("2024-03-18"), self.att("14.00", "11:00:00", 1000, "A2"))
        # re-check at 14.00: equity_now 8993.99 + 100 x 14.00 = 10393.99; position room 0.5 x 10393.99 - 1400 = 3796.995 -> permissible 3796.99 (< remaining 3993.99)
        # affordable at fill 14.02: floor(3796.99 / 14.02) = 270 -> 200 (est 2804.00 + 5.00 + 0.03 = 2809.03); downsized from 300
        rc = x2["outcome"]["recheck"]
        self.assertEqual((rc["equity_now"], rc["position_room"], rc["reservation_remaining"], rc["permissible"], rc["affordable_quantity"], rc["estimated_cost"]),
                         ("10393.99", "3796.99", "3993.99", "3796.99", 200, "2809.03"))
        # the gap downsizes the intent itself (declared contract): 100 + 200 = 300 shares, intent complete, reservation released
        self.assertEqual((x2["status"], x2["outcome"]["filled_quantity"], x2["outcome"]["fill_price"], x2["outcome"]["gap"]["code"]), ("filled", 200, "14.02", "gap_downsized"))
        self.assertEqual(x2["outcome"]["reservation"], {"symbol": A, "original_budget": "5000.00", "consumed": "3815.04", "remaining": "1184.96", "kind": "buy_cash_and_exposure"})
        self.assertEqual((E.intents()[iid]["quantity"], E.intents()[iid]["status"], E.reservations()["reserved_cash"]), (300, "filled", "0.00"))
        self.assertEqual(L.snapshot()["cash"], "6184.96")                                          # 10000 - 1006.01 - 2809.03 (3815.04 <= 5000)
        self.assertEqual(L.positions(), {A: 300})
        self.assertTrue(L.reconcile()["ok"])
        # current position room binds tighter than the stale reservation: after 100 @ 10, a 40.00 print values the holding at 4000 ->
        # equity 12993.99, position room 6496.995 - 4000 = 2496.99 < one lot (4004.00 + 5.00 + 0.04) -> cancelled although 3993.99 remained reserved
        E2, L2 = self.half()
        iid2 = self.intent(E2)
        E2.execute(iid2, ctx("2024-03-18"), self.att("10.00", "10:00:00", 100, "A1"))
        x3 = E2.execute(iid2, ctx("2024-03-18"), self.att("40.00", "11:00:00", 1000, "A2", band=("60.00", "3.00")))
        self.assertEqual((x3["status"], x3["reason"], x3["recheck"]["position_room"], x3["recheck"]["reservation_remaining"], x3["recheck"]["permissible"]),
                         ("cancelled", "gap_exceeds_budget", "2496.99", "3993.99", "2496.99"))
        self.assertEqual((L2.positions(), L2.snapshot()["cash"], E2.reservations()["reserved_cash"]), ({A: 100}, "8993.99", "0.00"))
        log("codex.p1_1.cumulative_budget", E, L)

    def test_same_price_repeated_minimum_commissions_accumulate_against_the_budget(self):
        E, L = self.half()
        iid = self.intent(E)
        for i, at in enumerate(("10:00:00", "10:30:00", "11:00:00", "11:30:00"), start=1):
            x = E.execute(iid, ctx("2024-03-18"), self.att("10.00", at, 100, f"A{i}"))
            self.assertEqual(x["outcome"]["filled_quantity"], 100)
        res = E.intents()[iid]["attempts"][-1]["reservation"]
        self.assertEqual((res["consumed"], res["remaining"]), ("4024.04", "975.96"))              # 4 x 1006.01 (four minimum commissions) vs 4009.04 for one fill
        self.assertEqual((E.intents()[iid]["status"], L.snapshot()["cash"], E.reservations()["reserved_cash"]), ("filled", "5975.96", "0.00"))

    def test_exact_boundary_and_reduced_remainder(self):
        # caps 1.0 so the reservation itself is the binding constraint: cash 2508.95 -> budget 2508.95 -> 200 shares (2002.00 + 5.00 + 0.02 = 2007.02; 300 would need 3008.03)
        E, L = self.half("2508.95", max_position_weight="1", max_gross_exposure="1")
        d = E.decide("D1", ctx("2024-03-18"), marks=(mark(A, "10.00", "2024-03-18"),), signals=(signal(A, "2024-03-18"),))
        self.assertEqual((self.entry(d, A)["quantity"], self.entry(d, A)["reserved_budget"]), (200, "2508.95"))
        x1 = E.execute("D1:buy:SYN_RISK_A", ctx("2024-03-18"), self.att("10.00", "10:00:00", 100, "A1"))
        self.assertEqual(x1["outcome"]["reservation"]["remaining"], "1502.94")                      # 2508.95 - 1006.01; cash also 1502.94
        # remainder 100 at 14.96 (fill 14.98): 1498.00 + 5.00 + 0.01 = 1503.01 > 1502.94 -> cancelled; at 14.95 (fill 14.97): 1497.00 + 5.00 + 0.01 = 1502.01 <= 1502.94 -> fills
        x2 = E.execute("D1:buy:SYN_RISK_A", ctx("2024-03-18"), self.att("14.96", "11:00:00", 1000, "A2"))
        self.assertEqual((x2["status"], x2["reason"], x2["recheck"]["permissible"]), ("cancelled", "gap_exceeds_budget", "1502.94"))
        E2, L2 = self.half("2508.95", max_position_weight="1", max_gross_exposure="1")
        E2.decide("D1", ctx("2024-03-18"), marks=(mark(A, "10.00", "2024-03-18"),), signals=(signal(A, "2024-03-18"),))
        E2.execute("D1:buy:SYN_RISK_A", ctx("2024-03-18"), self.att("10.00", "10:00:00", 100, "A1"))
        x3 = E2.execute("D1:buy:SYN_RISK_A", ctx("2024-03-18"), self.att("14.95", "11:00:00", 1000, "A2"))
        self.assertEqual((x3["status"], x3["outcome"]["fill_price"], x3["outcome"]["reservation"]["consumed"], x3["outcome"]["cash_after"]), ("filled", "14.97", "2508.02", "0.93"))

    def test_multiple_symbols_keep_separate_reservations_and_see_each_other(self):
        E, L = engine("100000.00", pol=policy(max_position_weight="0.30", max_gross_exposure="0.50", entry_phase="continuous"))
        d = E.decide("D1", ctx("2024-03-18"), marks=(mark(A, "10.00", "2024-03-18"), mark(B, "20.00", "2024-03-18")), signals=(signal(A, "2024-03-18"), signal(B, "2024-03-18")))
        self.assertEqual((self.entry(d, A)["reserved_budget"], self.entry(d, B)["reserved_budget"]), ("30000.00", "20000.00"))   # B: portfolio room 50000 - 30000
        xa = E.execute("D1:buy:SYN_RISK_A", ctx("2024-03-18"), self.att("10.00", "10:00:00", 1000, "A1"))
        self.assertEqual(xa["outcome"]["reservation"]["remaining"], "19984.90")                     # 30000 - (10010.00 + 5.00 + 0.10)
        xb = E.execute("D1:buy:SYN_RISK_B", ctx("2024-03-18"), evidence(B, "2024-03-19", "20.00", at="10:30:00", phase="continuous", capacity=100000, capacity_id="CAP-B1", attempt_id="B1"),
                       marks=(mark(A, "10.00", "2024-03-18"),))
        rc = xb["outcome"]["recheck"]
        # B re-check: cash 89984.90; A valued at its eligible 03-18 mark 10.00 -> 10000.00; equity 99984.90; portfolio room 0.5 x 99984.90 - 10000 - A's remaining 19984.90 = 20007.55
        self.assertEqual((rc["cash_now"], rc["gross_now"], rc["portfolio_room"], rc["reservation_remaining"]), ("89984.90", "10000.00", "20007.55", "20000.00"))
        self.assertEqual(xb["outcome"]["filled_quantity"], 900)                                    # 900 x 20.02 = 18018.00 + 5.41 + 0.18 = 18023.59 <= 20000
        # without a mark for the other holding the re-check is refused explicitly (no zero/cost fallback), state unchanged
        E2, _ = engine("100000.00", pol=policy(max_position_weight="0.30", max_gross_exposure="0.50", entry_phase="continuous"))
        E2.decide("D1", ctx("2024-03-18"), marks=(mark(A, "10.00", "2024-03-18"), mark(B, "20.00", "2024-03-18")), signals=(signal(A, "2024-03-18"), signal(B, "2024-03-18")))
        E2.execute("D1:buy:SYN_RISK_A", ctx("2024-03-18"), self.att("10.00", "10:00:00", 1000, "A1"))
        before = E2.intents()
        nb = E2.execute("D1:buy:SYN_RISK_B", ctx("2024-03-18"), evidence(B, "2024-03-19", "20.00", at="10:30:00", phase="continuous", capacity=100000, capacity_id="CAP-B1", attempt_id="B1"))
        self.assertEqual((nb["status"], nb["reason"], nb["symbols"], E2.intents()), ("refused", "valuation_incomplete", [A], before))


# ======================================================================================
class TestCodexReview01EvidenceValidation(RiskCase):
    """P1-2: invalid, mismatched or future execution evidence is an atomic refusal - never a cancellation, downsize or fill."""

    def pending(self, **kw):
        E, L = engine("10000.00", pol=policy(max_position_weight="0.50", max_gross_exposure="0.50", entry_phase="continuous", max_gap_pct="0.5", **kw))
        E.decide("D1", ctx("2024-03-18"), marks=(mark(A, "10.00", "2024-03-18"),), signals=(signal(A, "2024-03-18"),))
        return E, L, "D1:buy:SYN_RISK_A"

    def assertUntouched(self, E, before_intents, before_res, before_hash):
        self.assertEqual(E.intents(), before_intents)
        self.assertEqual(E.reservations(), before_res)
        self.assertNotEqual(E.chain_hash, before_hash)                                             # the refusal is an audit record only

    def test_future_price_cannot_cancel_a_valid_intent(self):
        E, L, iid = self.pending()
        before, res, h = E.intents(), E.reservations(), E.chain_hash
        ev = evidence(A, "2024-03-19", "100.00", at="10:00:00", phase="continuous")
        ev = replace(ev, price=replace(ev.price, observed_at="2024-03-20T10:00:00+08:00", available_at="2024-03-20T10:00:00+08:00"))
        x = E.execute(iid, ctx("2024-03-18"), ev)
        self.assertEqual((x["status"], x["reason"]), ("refused", "future_evidence"))
        self.assertUntouched(E, before, res, h)
        self.assertEqual(E.reservations()["reserved_cash"], "5000.00")

    def test_wrong_symbol_phase_and_early_attempts_are_refusals(self):
        E, L, iid = self.pending()
        before, res, h = E.intents(), E.reservations(), E.chain_hash
        wrong = evidence(B, "2024-03-19", "10.00", at="10:00:00", phase="continuous")
        self.assertEqual(E.execute(iid, ctx("2024-03-18"), wrong)["reason"], "invalid_evidence")
        self.assertEqual(E.execute(iid, ctx("2024-03-18"), evidence(A, "2024-03-19", "10.00", at="09:30:00", phase="open_auction"))["reason"], "phase_mismatch")
        early = evidence(A, "2024-03-19", "10.00", at="09:20:00", phase="continuous")                # after the decision instant, before eligible_from 09:30
        self.assertEqual(E.execute(iid, ctx("2024-03-18"), early)["reason"], "before_eligible")
        backdated = evidence(A, "2024-03-18", "10.00", at="14:00:00", phase="continuous")            # before the decision that created the intent (policy clock 16:00)
        self.assertEqual(E.execute(iid, ctx("2024-03-18"), backdated)["reason"], "chronology_violation")
        malformed = evidence(A, "2024-03-19", "10.00", at="10:00:00", phase="continuous")
        malformed = replace(malformed, price=replace(malformed.price, price=10.0))                   # float refused by the kernel dataclass
        self.assertEqual(E.execute(iid, ctx("2024-03-18"), malformed)["reason"], "invalid_evidence")
        self.assertUntouched(E, before, res, h)
        self.assertEqual(len(E.records), 6)

    def test_zero_affordability_with_valid_evidence_still_cancels_and_invalid_evidence_does_not(self):
        E, L, iid = self.pending()
        # 100.00 valid print (fill 100.10): one lot 10010.00 + 5.00 + 0.10 > permissible 5000 -> cancelled under the declared contract
        x = E.execute(iid, ctx("2024-03-18"), evidence(A, "2024-03-19", "100.00", at="10:00:00", phase="continuous", band=("200.00", "3.00")))
        self.assertEqual((x["status"], x["reason"], E.reservations()["reserved_cash"]), ("cancelled", "gap_exceeds_budget", "0.00"))
        # the same unaffordable print with an evidence defect the kernel would reject (band violation) is a refusal, not a cancellation
        E2, L2, iid2 = self.pending()
        before = E2.intents()
        bad = evidence(A, "2024-03-19", "100.00", at="10:00:00", phase="continuous", band=("50.00", "3.00"))   # observed 100.00 outside its own band
        x2 = E2.execute(iid2, ctx("2024-03-18"), bad)
        self.assertEqual((x2["status"], x2["reason"], x2["kernel_reasons"][0]["code"]), ("refused", "kernel_would_reject", "band_prices_invalid"))
        self.assertEqual((E2.intents(), E2.reservations()["reserved_cash"]), (before, "5000.00"))
        # normal path
        ok = E2.execute(iid2, ctx("2024-03-18"), evidence(A, "2024-03-19", "10.00", at="10:00:00", phase="continuous", capacity=1000))
        self.assertEqual((ok["status"], ok["outcome"]["filled_quantity"], ok["outcome"]["cash_after"]), ("filled", 400, "5990.96"))   # 4004.00 + 5.00 + 0.04


# ======================================================================================
class TestCodexReview01ContextBinding(RiskCase):
    """P1-3: the decision context (calendar prefix through expiry, clocks, fee/assumption semantics, phase) is bound at intent creation."""

    def pending(self, **kw):
        E, L = engine("100000.00", pol=policy(entry_phase="continuous", **kw))
        d = E.decide("D1", ctx("2024-03-18"), marks=(mark(A, "10.00", "2024-03-18"),), signals=(signal(A, "2024-03-18"),))
        it = E.intents()["D1:buy:SYN_RISK_A"]
        self.assertEqual((it["phase"], it["expiry_session"], it["expires_at"], it["context"]["calendar_prefix"]["last"]), ("continuous", "2024-03-19", "2024-03-19T15:00:00+08:00", "2024-03-19"))
        return E, L, "D1:buy:SYN_RISK_A"

    def test_first_fill_after_original_expiry_with_a_rewritten_calendar_is_refused(self):
        E, L, iid = self.pending()
        before, res = E.intents(), E.reservations()
        rewritten = r.DecisionContext("2024-03-18", "2024-03-18T16:00:00+08:00", replace(CAL, close_time="16:00"), FEES, ASM)
        x = E.execute(iid, rewritten, evidence(A, "2024-03-19", "10.00", at="15:30:00", phase="continuous"))
        self.assertEqual((x["status"], x["reason"], x["changed"]), ("refused", "context_mismatch", ["calendar_clock", "calendar_prefix"]))
        self.assertEqual((E.intents(), E.reservations(), L.positions()), (before, res, {}))
        # the original calendar: a valid attempt after the bound 15:00 expiry expires the intent deterministically and releases the reservation
        x2 = E.execute(iid, ctx("2024-03-18"), evidence(A, "2024-03-19", "10.00", at="15:30:00", phase="continuous", attempt_id="A2"))
        self.assertEqual((x2["status"], x2["released_remaining"], E.reservations()["reserved_cash"], L.positions()), ("expired", "20000.00", "0.00", {}))
        self.assertEqual(E.intents()[iid]["status"], "expired")
        self.assertEqual(E.execute(iid, ctx("2024-03-18"), evidence(A, "2024-03-19", "10.00", at="14:00:00", phase="continuous", attempt_id="A3"))["status"], "refused")
        log("codex.p1_3.context_binding", E, L)

    def test_relevant_context_changes_are_refused_and_suffix_freedom_kept(self):
        variants = {
            "tz_offset": r.DecisionContext("2024-03-18", "2024-03-18T16:00:00+08:00", replace(CAL, tz_offset="+09:00"), FEES, ASM),
            "halt_in_window": r.DecisionContext("2024-03-18", "2024-03-18T16:00:00+08:00", replace(CAL, halted_sessions=("2024-03-19",)), FEES, ASM),
            "fee_schedule": r.DecisionContext("2024-03-18", "2024-03-18T16:00:00+08:00", CAL, replace(FEES, min_commission="6.00"), ASM),
            "assumptions": r.DecisionContext("2024-03-18", "2024-03-18T16:00:00+08:00", CAL, FEES, replace(ASM, slippage_rate="0.002")),
        }
        for name, c in variants.items():
            with self.subTest(name):
                E, L, iid = self.pending()
                before = E.intents()
                x = E.execute(iid, c, evidence(A, "2024-03-19", "10.00", at="10:00:00", phase="continuous"))
                self.assertEqual((x["status"], x["reason"]), ("refused", "context_mismatch"))
                self.assertEqual(E.intents(), before)
        E, L, iid = self.pending()
        suffix = r.DecisionContext("2024-03-18", "2024-03-18T16:00:00+08:00", replace(CAL, sessions=SESSIONS + ("2024-03-28",), halted_sessions=("2024-03-27",)), FEES, ASM)
        ok = E.execute(iid, suffix, evidence(A, "2024-03-19", "10.00", at="10:00:00", phase="continuous", capacity=5000))
        self.assertEqual((ok["status"], ok["outcome"]["filled_quantity"]), ("filled", 1900))

    def test_expired_intent_is_swept_at_the_next_decision_without_fabricated_fills(self):
        E, L, iid = self.pending()
        d2 = E.decide("D2", ctx("2024-03-19"), marks=(mark(A, "10.00", "2024-03-19"),))
        self.assertEqual(d2["expired_intents"], [{"intent_id": iid, "expires_at": "2024-03-19T15:00:00+08:00", "released_remaining": "20000.00"}])
        self.assertEqual((E.intents()[iid]["status"], E.reservations()["reserved_cash"], L.positions(), L.snapshot()["cash"]), ("expired", "0.00", {}, "100000.00"))
        d3 = E.decide("D3", ctx("2024-03-20"), marks=(mark(A, "10.00", "2024-03-20"),), signals=(signal(A, "2024-03-20"),))
        self.assertEqual(self.entry(d3, A)["decision"], "buy")                                     # re-evaluated fresh


# ======================================================================================
class TestCodexReview01Chronology(RiskCase):
    """P1-4: decisions and valuation views never consume ledger state from after their own instant."""

    def filled(self):
        E, L = engine("100000.00", pol=policy(entry_phase="continuous"))
        E.decide("D1", ctx("2024-03-18"), marks=(mark(A, "10.00", "2024-03-18"),), signals=(signal(A, "2024-03-18"),))
        x = E.execute("D1:buy:SYN_RISK_A", ctx("2024-03-18"), evidence(A, "2024-03-19", "10.00", at="10:00:00", phase="continuous", capacity=5000))
        self.assertEqual(x["status"], "filled")
        return E, L

    def test_backdated_decision_and_performance_are_refused_and_earlier_records_kept(self):
        E, L = self.filled()
        earlier = [x["record_hash"] for x in E.records]
        back = E.decide("D-back", ctx("2024-03-18"), marks=(mark(A, "10.00", "2024-03-18"),))
        self.assertEqual((back["status"], back["refusals"][0]["code"], back["refusals"][0]["ledger_last_executed_at"]), ("refused", "chronology_violation", "2024-03-19T10:00:00+08:00"))
        self.assertNotIn("valuation", back)
        perf = E.performance(r.DecisionContext("2024-03-19", "2024-03-19T09:00:00+08:00", CAL, FEES, ASM), marks=(mark(A, "10.00", "2024-03-18"),), start_session="2024-03-18", initial_cash="100000.00")
        self.assertEqual((perf["status"], perf["reason"], perf["complete"], perf["equity"]), ("refused", "chronology_violation", False, None))
        self.assertEqual([x["record_hash"] for x in E.records[: len(earlier)]], earlier)
        nxt = E.decide("D2", ctx("2024-03-19"), marks=(mark(A, "10.30", "2024-03-19"),))
        self.assertEqual((nxt["status"], nxt["valuation"]["positions"][A]["quantity"], nxt["valuation"]["equity"]), ("decided", 1900, "100545.10"))   # cash 80975.10 + 1900 x 10.30
        log("codex.p1_4.chronology", E, L)

    def test_same_instant_ordering_is_allowed(self):
        E, L = engine("100000.00", lots=(lm.InitialLot(A, 1000, "2024-03-18", "10073.12", "syn:opening"),), pol=policy(exit_phase="close_auction"))
        E.decide("D1", ctx("2024-03-19"), marks=(mark(A, "9.00", "2024-03-19"),))                    # stop -> exit intent for 03-20
        x = E.execute("D1:sell:SYN_RISK_A", ctx("2024-03-19"), evidence(A, "2024-03-20", "9.00", at="15:00:00", phase="close_auction"))
        self.assertEqual(x["status"], "filled")
        same = E.decide("D2", ctx("2024-03-20", decided="15:00:00"), marks=(mark(A, "9.00", "2024-03-20", observed="15:00:00", available="15:00:00"),))
        self.assertEqual((same["status"], same["valuation"]["positions"]), ("decided", {}))


# ======================================================================================
class TestCodexReview02MarkSelection(RiskCase):
    """Review 02 P1-1: one causal mark-selection contract for decision, execution and performance valuation - aware
    instants, the LATEST observation wins, conflicting values at the latest instant are refused, equivalent spellings
    are one value, input order is irrelevant and the selected mark is bound in the record."""

    HELD = (lm.InitialLot(B, 1000, "2024-03-15", "1000.00", "syn:other-lot"),)

    def other(self, **kw):
        base = dict(max_position_weight="0.50", max_gross_exposure="0.50", entry_phase="continuous", max_gap_pct="0.5")
        base.update(kw)
        E, L = engine("10000.00", lots=self.HELD, pol=policy(**base))
        d = E.decide("D1", ctx("2024-03-18"), marks=(mark(A, "10.00", "2024-03-18"), mark(B, "1.00", "2024-03-18")), signals=(signal(A, "2024-03-18"),))
        e = self.entry(d, A)
        # equity 10000 + 1000 x 1.00 = 11000; position room 5500; portfolio room 5500 - 1000 = 4500; cash room 10000 -> budget 4500.00
        # reserved price 10.01; floor(4500 / 10.01) = 449 -> 400; estimate 4004.00 + 5.00 + 0.04 = 4009.04
        self.assertEqual((e["quantity"], e["reserved_budget"], e["estimated_cost"], e["rooms"]["portfolio_room"]), (400, "4500.00", "4009.04", "4500.00"))
        return E, L, "D1:buy:SYN_RISK_A"

    def bmark(self, price, observed, session="2024-03-19", available=None, source="syn:other-feed"):
        return r.Mark(B, price, f"{session}T{observed}+08:00", f"{session}T{available or observed}+08:00", source, True)

    def att(self, price="10.00", at="10:00:00", capacity=1000, attempt_id="A1", session="2024-03-19"):
        return evidence(A, session, price, at=at, phase="continuous", capacity=capacity, capacity_id=f"CAP-{attempt_id}", attempt_id=attempt_id)

    def test_execution_recheck_uses_the_latest_mark_regardless_of_input_order(self):
        old, latest = self.bmark("1.00", "09:00:00"), self.bmark("20.00", "09:45:00")
        results = {}
        for name, marks in (("latest_only", (latest,)), ("old_plus_latest", (old, latest)), ("latest_plus_old", (latest, old)),
                            ("equivalent_spellings", (self.bmark("20", "09:45:00"), latest, self.bmark("20.0", "09:45:00")))):
            E, L, iid = self.other()
            x = E.execute(iid, ctx("2024-03-18"), self.att(), marks=marks)
            # latest B mark 20.00 -> gross_now 20000.00, equity_now 30000.00; position room 15000.00; portfolio room 15000 - 20000 = -5000.00 -> permissible -5000.00
            rc = x["recheck"]
            self.assertEqual((x["status"], x["reason"], rc["gross_now"], rc["equity_now"], rc["portfolio_room"], rc["permissible"], rc["affordable_quantity"]),
                             ("cancelled", "gap_exceeds_budget", "20000.00", "30000.00", "-5000.00", "-5000.00", 0), name)
            self.assertEqual(rc["marks"][B], {"price": "20.00", "observed_at": "2024-03-19T09:45:00+08:00", "available_at": "2024-03-19T09:45:00+08:00", "source_ref": "syn:other-feed",
                                              "session": "2024-03-19", "age_sessions": 0, "quantity": 1000, "value": "20000.00"}, name)
            self.assertEqual((rc["target"]["observed_price"], rc["target"]["price_observed_at"], rc["refused_marks"]), ("10.00", "2024-03-19T10:00:00+08:00", []))
            self.assertEqual((L.positions(), E.reservations()["reserved_cash"]), ({B: 1000}, "0.00"), name)
            results[name] = x["record_hash"]
        self.assertEqual(len(set(results.values())), 1, results)                          # the input order and equivalent spellings leave no trace in the record
        # positive control: the latest mark is the low one -> gross_now 1000.00, equity 11000.00, rooms 5500 / 4500 / 10000, remaining 4500 -> 400 @ 10.01 = 4009.04
        for marks in ((self.bmark("20.00", "09:00:00"), self.bmark("1.00", "09:45:00")), (self.bmark("1.00", "09:45:00"), self.bmark("20.00", "09:00:00"))):
            E, L, iid = self.other()
            x = E.execute(iid, ctx("2024-03-18"), self.att(), marks=marks)
            rc = x["outcome"]["recheck"]
            self.assertEqual((x["status"], x["outcome"]["filled_quantity"], x["outcome"]["cash_after"], rc["gross_now"], rc["equity_now"], rc["permissible"]),
                             ("filled", 400, "5990.96", "1000.00", "11000.00", "4500.00"))
            self.assertEqual((rc["marks"][B]["price"], rc["marks"][B]["observed_at"]), ("1.00", "2024-03-19T09:45:00+08:00"))
            self.assertEqual(L.positions(), {A: 400, B: 1000})
        log("codex.p2_1.mark_selection", E, L)

    def test_conflicting_marks_at_the_latest_instant_are_an_atomic_refusal_in_both_orders(self):
        hi, lo = self.bmark("20.00", "09:45:00"), self.bmark("1.00", "09:45:00", source="syn:other-feed-2")
        hashes = []
        for marks in ((hi, lo), (lo, hi)):
            E, L, iid = self.other()
            before, res, h = E.intents(), E.reservations(), E.chain_hash
            x = E.execute(iid, ctx("2024-03-18"), self.att(), marks=marks)
            self.assertEqual((x["status"], x["reason"], x["symbols"]), ("refused", "valuation_incomplete", [B]))
            self.assertEqual((x["unresolved"][B]["code"], x["unresolved"][B]["conflicting_prices"], x["unresolved"][B]["observed_at"]),
                             ("inconsistent_evidence", ["1.00", "20.00"], "2024-03-19T09:45:00+08:00"))
            self.assertEqual((E.intents(), E.reservations(), E.reservations()["reserved_cash"], L.positions()), (before, res, "4500.00", {B: 1000}))
            self.assertNotEqual(E.chain_hash, h)                                              # audit record only
            hashes.append(x["record_hash"])
        self.assertEqual(hashes[0], hashes[1])
        # an older conflict is irrelevant once a later unambiguous mark exists; a tz re-spelling of the same instant is the same instant
        E, L, iid = self.other()
        utc_same = r.Mark(B, "20.00", "2024-03-19T01:45:00+00:00", "2024-03-19T01:45:00+00:00", "syn:other-feed", True)   # == 09:45 +08:00
        x = E.execute(iid, ctx("2024-03-18"), self.att(), marks=(self.bmark("1.00", "09:00:00"), self.bmark("5.00", "09:00:00"), hi, utc_same))
        self.assertEqual((x["status"], x["recheck"]["marks"][B]["price"]), ("cancelled", "20.00"))
        E, L, iid = self.other()
        utc_other = r.Mark(B, "1.00", "2024-03-19T01:45:00+00:00", "2024-03-19T01:45:00+00:00", "syn:other-feed", True)
        x = E.execute(iid, ctx("2024-03-18"), self.att(), marks=(hi, utc_other))
        self.assertEqual((x["status"], x["reason"], x["unresolved"][B]["conflicting_prices"]), ("refused", "valuation_incomplete", ["1.00", "20.00"]))

    def test_missing_stale_and_future_only_held_marks_are_refused_not_zero(self):
        E, L, iid = self.other()
        before = E.intents()
        x = E.execute(iid, ctx("2024-03-18"), self.att(), marks=())
        self.assertEqual((x["status"], x["reason"], x["unresolved"][B]["code"], E.intents()), ("refused", "valuation_incomplete", "missing_mark", before))
        # future-only: a 10:30 mark for a 10:00 attempt is refused as future evidence and no fallback remains
        x = E.execute(iid, ctx("2024-03-18"), self.att(attempt_id="A2"), marks=(self.bmark("1.00", "10:30:00"),))
        self.assertEqual((x["reason"], x["unresolved"][B]["code"], x["refused_marks"][0]["code"]), ("valuation_incomplete", "missing_mark", "future_evidence"))
        # stale: with a two-session intent an attempt on 03-20 may use marks of age <= 1 (03-19 / 03-20); a 03-18 mark is age 2
        E2, L2, iid2 = self.other(intent_expiry_sessions=2)
        x = E2.execute(iid2, ctx("2024-03-18"), self.att(at="10:00:00", session="2024-03-20"), marks=(self.bmark("1.00", "15:00:00", session="2024-03-18"),))
        self.assertEqual((x["reason"], x["unresolved"][B]["code"], x["unresolved"][B]["age_sessions"], x["unresolved"][B]["max_age"]), ("valuation_incomplete", "stale_mark", 2, 1))
        x = E2.execute(iid2, ctx("2024-03-18"), self.att(at="10:00:00", session="2024-03-20", attempt_id="A3"), marks=(self.bmark("1.00", "15:00:00", session="2024-03-19"),))
        self.assertEqual((x["status"], x["outcome"]["filled_quantity"], x["outcome"]["recheck"]["marks"][B]["age_sessions"]), ("filled", 400, 1))
        self.assertEqual(L2.positions(), {A: 400, B: 1000})

    def test_decision_and_performance_valuation_take_the_latest_same_session_mark(self):
        E, L = engine("10000.00", lots=self.HELD)
        older, newer = self.bmark("1.00", "14:00:00"), self.bmark("20.00", "15:00:00")
        d = E.decide("D1", ctx("2024-03-19"), marks=(older, newer))
        v = d["valuation"]
        self.assertEqual((v["equity"], v["positions"][B]["mark"], v["positions"][B]["mark_observed_at"], v["positions"][B]["mark_age_sessions"]), ("30000.00", "20.00", "2024-03-19T15:00:00+08:00", 0))
        E2, _ = engine("10000.00", lots=self.HELD)
        self.assertEqual(E2.decide("D1", ctx("2024-03-19"), marks=(newer, older))["record_hash"], d["record_hash"])
        perf = E.performance(ctx("2024-03-19"), marks=(older, newer), start_session="2024-03-18", initial_cash="10000.00")
        perf2 = E2.performance(ctx("2024-03-19"), marks=(newer, older), start_session="2024-03-18", initial_cash="10000.00")
        self.assertEqual((perf["equity"], perf["positions"][B]["mark_evidence"]["observed_at"], perf), ("30000.00", "2024-03-19T15:00:00+08:00", perf2))
        # a same-instant conflict on the held symbol makes the valuation incomplete in both orders (buys refused, position kept)
        for marks in ((newer, self.bmark("1.00", "15:00:00")), (self.bmark("1.00", "15:00:00"), newer)):
            E3, _ = engine("10000.00", lots=self.HELD)
            d3 = E3.decide("D1", ctx("2024-03-19"), marks=marks + (mark(A, "10.00", "2024-03-19"),), signals=(signal(A, "2024-03-19"),))
            self.assertEqual((d3["valuation"]["complete"], d3["valuation"]["positions"][B]["unresolved_reason"]["conflicting_prices"], self.entry(d3, A)["reason"]),
                             (False, ["1.00", "20.00"], "valuation_incomplete"))
        # statuses and benchmark levels follow the same rule: conflicting values at the latest instant are inconsistent evidence, not a pick
        E4, _ = engine("10000.00")
        d4 = E4.decide("D1", ctx("2024-03-19"), marks=(mark(A, "10.00", "2024-03-19"),), signals=(signal(A, "2024-03-19"),),
                       statuses=(status(A, "suspended", "2024-03-19"), status(A, "listed", "2024-03-19")), benchmark=(bench("3000.00", "2024-03-19"), bench("2990.00", "2024-03-19")))
        self.assertEqual((self.entry(d4, A)["reason"], d4["benchmark"]["status"], d4["benchmark"]["level"], d4["benchmark"]["conflicting_levels"]),
                         ("inconsistent_evidence", "inconsistent_evidence", None, ["2990.00", "3000.00"]))
        d5 = E4.decide("D2", ctx("2024-03-20"), marks=(mark(A, "10.00", "2024-03-20"),), signals=(signal(A, "2024-03-20"),),
                       statuses=(status(A, "suspended", "2024-03-20", observed="14:00:00", available="14:00:00"), status(A, "listed", "2024-03-20")))
        self.assertEqual(self.entry(d5, A)["decision"], "buy")                                   # the latest status (15:00 listed) wins over the older suspension


# ======================================================================================
class TestCodexReview02PolicyChronology(RiskCase):
    """Review 02 P1-2: the policy-wide event clock (decisions, state-changing attempts, cancellations) and the ledger's
    last recorded attempt gate EVERY state-changing path before any mutation - including zero-affordability
    cancellation, expiry at attempt and explicit cancellation; earlier events are audit-only refusals."""

    def half(self, cash="10000.00", **kw):
        base = dict(max_position_weight="0.50", max_gross_exposure="0.50", entry_phase="continuous", max_gap_pct="0.5")
        base.update(kw)
        return engine(cash, pol=policy(**base))

    def att(self, price, at, capacity, attempt_id, band=("30.00", "3.00"), session="2024-03-19"):
        return evidence(A, session, price, at=at, phase="continuous", capacity=capacity, capacity_id=f"CAP-{attempt_id}", attempt_id=attempt_id, band=band)

    def partial(self):
        E, L = self.half()
        E.decide("D1", ctx("2024-03-18"), marks=(mark(A, "10.00", "2024-03-18"),), signals=(signal(A, "2024-03-18"),))
        x1 = E.execute("D1:buy:SYN_RISK_A", ctx("2024-03-18"), self.att("10.00", "11:00:00", 100, "A1"))
        # 100 @ 10.01 = 1001.00 + 5.00 + 0.01 = 1006.01 -> cash 8993.99; reservation 5000.00 - 1006.01 = 3993.99 remaining
        self.assertEqual((x1["status"], x1["outcome"]["filled_quantity"], x1["outcome"]["cash_after"], x1["outcome"]["reservation"]["remaining"]), ("partially_filled", 100, "8993.99", "3993.99"))
        return E, L, "D1:buy:SYN_RISK_A"

    def assertRefusedUntouched(self, E, L, x, before, res, clock, ledger_last):
        self.assertEqual((x["status"], x["reason"], x["policy_event_clock"], x["ledger_last_executed_at"]), ("refused", "chronology_violation", clock, ledger_last))
        self.assertEqual((E.intents(), E.reservations()), (before, res))
        self.assertEqual(E.records[-1]["state_summary"]["event_clock"], clock)

    def test_backdated_cancellation_downsize_and_fill_paths_are_refused_before_any_mutation(self):
        E, L, iid = self.partial()
        before, res = E.intents(), E.reservations()
        # exact review case: a structurally valid 10:00 attempt with a contemporaneous 100.00 print inside an explicit 200 band
        x = E.execute(iid, ctx("2024-03-18"), self.att("100.00", "10:00:00", 1000, "A-earlier", band=("200.00", "3.00")))
        self.assertRefusedUntouched(E, L, x, before, res, "2024-03-19T11:00:00+08:00", "2024-03-19T11:00:00+08:00")
        self.assertNotIn("recheck", x)                                                              # refused before the re-check valued anything
        # backdated affordable attempt (would fill 300) and backdated downsize print (14.00) are refused the same way
        for price, aid in (("10.00", "A-fill"), ("14.00", "A-gap")):
            x = E.execute(iid, ctx("2024-03-18"), self.att(price, "10:30:00", 1000, aid))
            self.assertRefusedUntouched(E, L, x, before, res, "2024-03-19T11:00:00+08:00", "2024-03-19T11:00:00+08:00")
        self.assertEqual((L.positions(), L.snapshot()["cash"], E.reservations()["by_intent"][iid]["remaining"]), ({A: 100}, "8993.99", "3993.99"))
        # same-instant control: 11:00 again with a new attempt id is allowed and ordered by sequence
        # cash 8993.99; target 100 @ 10.00 = 1000.00; equity 9993.99; position room 4996.995 - 1000 = 3996.99; portfolio room 3996.99; remaining 3993.99 -> permissible 3993.99
        # floor(3993.99 / 10.01) = 399 -> 300 (cap 300); 3003.00 + 5.00 + 0.03 = 3008.03 -> cash 5985.96; total spent 4014.04 <= 5000
        same = E.execute(iid, ctx("2024-03-18"), self.att("10.00", "11:00:00", 1000, "A2"))
        rc = same["outcome"]["recheck"]
        self.assertEqual((same["status"], same["outcome"]["filled_quantity"], same["outcome"]["cash_after"], rc["permissible"], rc["position_room"], rc["target"]["held_quantity"]),
                         ("filled", 300, "5985.96", "3993.99", "3996.99", 100))
        self.assertEqual((E.reservations()["reserved_cash"], same["outcome"]["reservation"]["consumed"], L.positions()), ("0.00", "4014.04", {A: 400}))
        # valid chronological control: a later decision values the 400 shares; a backdated decision is refused by both clocks
        d2 = E.decide("D2", ctx("2024-03-19"), marks=(mark(A, "10.00", "2024-03-19"),))
        self.assertEqual((d2["status"], d2["valuation"]["equity"]), ("decided", "9985.96"))          # 5985.96 + 400 x 10.00
        back = E.decide("D-back", ctx("2024-03-19", decided="15:30:00"), marks=(mark(A, "10.00", "2024-03-19"),))
        self.assertEqual((back["status"], back["refusals"][0]["code"], back["refusals"][0]["policy_event_clock"]), ("refused", "chronology_violation", "2024-03-19T16:00:00+08:00"))
        log("codex.p2_2.policy_chronology", E, L)

    def test_expiry_and_cancellation_clocks_gate_earlier_attempts_and_decisions(self):
        E, L = self.half(max_position_weight="0.25")
        d = E.decide("D1", ctx("2024-03-18"), marks=(mark(A, "10.00", "2024-03-18"), mark(B, "20.00", "2024-03-18")), signals=(signal(A, "2024-03-18"), signal(B, "2024-03-18")))
        # A: position room 2500 -> 200 @ 10.01 (2002.00 + 5.00 + 0.02 = 2007.02); B: portfolio room 5000 - 2500 = 2500 -> 100 @ 20.02 (2002.00 + 5.00 + 0.02 = 2007.02)
        self.assertEqual((self.entry(d, A)["quantity"], self.entry(d, B)["quantity"], E.reservations()["reserved_cash"]), (200, 100, "5000.00"))
        # a valid attempt after A's bound expiry (03-19 15:00) expires A and moves the policy clock to 15:30 without any ledger event
        late = E.execute("D1:buy:SYN_RISK_A", ctx("2024-03-18"), self.att("10.00", "15:30:00", 1000, "A-late"))
        self.assertEqual((late["status"], late["released_remaining"], E.reservations()["reserved_cash"], L.snapshot()["last_executed_at"]), ("expired", "2500.00", "2500.00", None))
        self.assertEqual(E.records[-1]["state_summary"]["event_clock"], "2024-03-19T15:30:00+08:00")
        # an earlier attempt on B (14:00) and an earlier decision (15:00) are refused; B keeps its reservation
        before, res = E.intents(), E.reservations()
        xb = E.execute("D1:buy:SYN_RISK_B", ctx("2024-03-18"), evidence(B, "2024-03-19", "20.00", at="14:00:00", phase="continuous", capacity=1000, capacity_id="CAP-B", attempt_id="B1"))
        self.assertRefusedUntouched(E, L, xb, before, res, "2024-03-19T15:30:00+08:00", None)
        early = E.decide("D-early", ctx("2024-03-19", decided="15:00:00"), marks=(mark(B, "20.00", "2024-03-19"),))
        self.assertEqual((early["status"], early["refusals"][0]["code"], early["refusals"][0]["ledger_last_executed_at"]), ("refused", "chronology_violation", None))
        self.assertEqual((E.intents(), E.reservations()), (before, res))
        # an explicit cancellation carries its own instant under the same rule: earlier than the clock -> refused; valid -> cancelled and the clock advances
        bad = E.cancel("D1:buy:SYN_RISK_B", "fixture", at="2024-03-19T15:00:00+08:00")
        self.assertEqual((bad["status"], bad["reason_code"], bad["policy_event_clock"], E.reservations()["reserved_cash"]), ("refused", "chronology_violation", "2024-03-19T15:30:00+08:00", "2500.00"))
        ok = E.cancel("D1:buy:SYN_RISK_B", "fixture", at="2024-03-19T15:45:00+08:00")
        self.assertEqual((ok["status"], ok["released_remaining"], ok["at"], E.reservations()["reserved_cash"]), ("cancelled", "2500.00", "2024-03-19T15:45:00+08:00", "0.00"))
        self.assertEqual(E.records[-1]["state_summary"]["event_clock"], "2024-03-19T15:45:00+08:00")
        d15 = E.decide("D-1540", ctx("2024-03-19", decided="15:40:00"), marks=(mark(B, "20.00", "2024-03-19"),))
        self.assertEqual((d15["status"], d15["refusals"][0]["policy_event_clock"]), ("refused", "2024-03-19T15:45:00+08:00"))
        d2 = E.decide("D2", ctx("2024-03-19"), marks=(mark(A, "10.00", "2024-03-19"), mark(B, "20.00", "2024-03-19")), signals=(signal(A, "2024-03-19"), signal(B, "2024-03-19")))
        self.assertEqual((d2["status"], d2["expired_intents"], self.entry(d2, A)["decision"], self.entry(d2, B)["decision"]), ("decided", [], "buy", "buy"))
        self.assertEqual((L.positions(), L.snapshot()["cash"], L.snapshot()["last_executed_at"]), ({}, "10000.00", None))
        # a cancellation without an instant is stamped at the current clock and can never be placed earlier than the state it changes
        stamped = E.cancel("D2:buy:SYN_RISK_A", "fixture")
        self.assertEqual((stamped["status"], stamped["at"]), ("cancelled", "2024-03-19T16:00:00+08:00"))

    def test_refusals_and_duplicates_never_advance_the_clock(self):
        E, L, iid = self.partial()
        clock_before = E.records[-1]["state_summary"]["event_clock"]
        E.execute(iid, ctx("2024-03-18"), self.att("10.00", "12:00:00", 1000, "A1"))                                       # duplicate id -> duplicate
        self.assertEqual((E.records[-1]["status"], E.records[-1]["state_summary"]["event_clock"]), ("duplicate", clock_before))
        bad = evidence(B, "2024-03-19", "10.00", at="12:00:00", phase="continuous", attempt_id="A9")                      # wrong symbol -> refused
        self.assertEqual((E.execute(iid, ctx("2024-03-18"), bad)["reason"], E.records[-1]["state_summary"]["event_clock"]), ("invalid_evidence", clock_before))
        fut = replace(self.att("10.00", "12:00:00", 1000, "A8"), price=replace(self.att("10.00", "12:00:00", 1000, "A8").price, observed_at="2024-03-19T12:30:00+08:00", available_at="2024-03-19T12:30:00+08:00"))
        self.assertEqual((E.execute(iid, ctx("2024-03-18"), fut)["reason"], E.records[-1]["state_summary"]["event_clock"]), ("future_evidence", clock_before))
        # after those refusals an 11:30 attempt (later than the 11:00 clock) is still valid
        ok = E.execute(iid, ctx("2024-03-18"), self.att("10.00", "11:30:00", 1000, "A2"))
        self.assertEqual((ok["status"], ok["outcome"]["filled_quantity"], E.records[-1]["state_summary"]["event_clock"]), ("filled", 300, "2024-03-19T11:30:00+08:00"))


# ======================================================================================
class TestImmutabilityAndDeterminism(RiskCase):
    def run_prefix(self, E):
        E.decide("D1", ctx("2024-03-18"), marks=(mark(A, "10.00", "2024-03-18"),), signals=(signal(A, "2024-03-18"),), benchmark=(bench("3000.00", "2024-03-18"),))
        E.execute("D1:buy:SYN_RISK_A", ctx("2024-03-18"), evidence(A, "2024-03-19", "10.05"))
        E.decide("D2", ctx("2024-03-19"), marks=(mark(A, "10.30", "2024-03-19"),), benchmark=(bench("3030.00", "2024-03-19"),))

    def test_later_information_does_not_change_earlier_records_or_hashes(self):
        a, _ = engine(); self.run_prefix(a)
        prefix, prefix_hash = list(a.records), a.chain_hash
        b, _ = engine(); self.run_prefix(b)
        self.assertEqual(list(b.records), prefix)
        self.assertEqual(b.chain_hash, prefix_hash)
        b.decide("D3", ctx("2024-03-20"), marks=(mark(A, "9.50", "2024-03-20"),), benchmark=(bench("2990.00", "2024-03-20"),))
        b.execute("D3:sell:SYN_RISK_A", ctx("2024-03-20"), evidence(A, "2024-03-21", "9.40", attempt_id="A2"))
        self.assertEqual(list(b.records)[:3], prefix)
        self.assertEqual([x["record_hash"] for x in b.records[:3]], [x["record_hash"] for x in prefix])
        self.assertNotEqual(b.chain_hash, prefix_hash)
        # information strictly after D2 (a later mark) handed to a fresh engine with the same history yields the same D2 record
        c, _ = engine(); self.run_prefix(c)
        self.assertEqual(c.records[2]["record_hash"], prefix[2]["record_hash"])

    def test_numeric_spelling_and_caller_context_do_not_change_results(self):
        ref, _ = engine("100000.00"); self.run_prefix(ref)
        with decimal.localcontext() as c:
            c.prec, c.rounding = 6, decimal.ROUND_DOWN
            c.traps[decimal.Inexact] = True
            e, _ = engine(Decimal("100000"));
            e.decide("D1", ctx("2024-03-18"), marks=(mark(A, Decimal("10"), "2024-03-18"),), signals=(signal(A, "2024-03-18"),), benchmark=(bench(3000, "2024-03-18"),))
            e.execute("D1:buy:SYN_RISK_A", ctx("2024-03-18"), evidence(A, "2024-03-19", Decimal("10.050")))
            e.decide("D2", ctx("2024-03-19"), marks=(mark(A, "10.30", "2024-03-19"),), benchmark=(bench("3030.00", "2024-03-19"),))
            self.assertEqual(c.prec, 6)
        self.assertEqual([x["record_hash"] for x in e.records], [x["record_hash"] for x in ref.records])

    def test_views_are_detached_and_refusals_are_atomic(self):
        E, L = engine(); self.run_prefix(E)
        before_hash, before_intents = E.chain_hash, E.intents()
        rec = E.records[0]; rec["entries"][0]["quantity"] = 999
        intents = E.intents(); intents["D1:buy:SYN_RISK_A"]["status"] = "tampered"
        self.assertEqual(E.records[0]["entries"][0]["quantity"], 1900)
        self.assertEqual(E.intents(), before_intents)
        bad = E.execute("nope", ctx("2024-03-19"), evidence(A, "2024-03-20", "10.00"))
        self.assertEqual(bad["status"], "refused")
        self.assertEqual(E.intents(), before_intents)                                   # nothing changed except the audit chain
        self.assertNotEqual(E.chain_hash, before_hash)                                  # the refusal itself is an audit record
        self.assertEqual(E.records[-1]["state_summary"]["ledger_state_hash"], L.state_hash)

    def test_module_is_stdlib_only_and_frozen_modules_are_the_pinned_bytes(self):
        self.assertEqual(hashlib.sha256(KERNEL_PATH.read_bytes()).hexdigest(), FROZEN["kernel"])
        self.assertEqual(hashlib.sha256(LEDGER_PATH.read_bytes()).hexdigest(), FROZEN["ledger"])
        tree = ast.parse(RISK_PATH.read_text(encoding="utf-8"))
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(a.name.split(".")[0] for a in node.names)
            elif isinstance(node, ast.ImportFrom):
                imported.add((node.module or "").split(".")[0])
        self.assertTrue(imported <= {"__future__", "copy", "hashlib", "json", "dataclasses", "datetime", "decimal", "typing"}, imported)
        calls = {n.func.attr if isinstance(n.func, ast.Attribute) else getattr(n.func, "id", None) for n in ast.walk(tree) if isinstance(n, ast.Call)}
        for forbidden in ("now", "utcnow", "today", "open", "getenv", "environ", "connect", "system", "popen", "run"):
            self.assertNotIn(forbidden, calls, forbidden)
        self.assertFalse(any(name == "app" or name.startswith("app.") for name in sys.modules))
        self.assertEqual(r.RISK_POLICY_HASH, r.sha256_text(r.canonical_json(r.RISK_POLICY)))
        self.assertEqual((r.RISK_POLICY["kernel"]["policy_hash"], r.RISK_POLICY["ledger"]["policy_hash"]), (k.POLICY_HASH, lm.LEDGER_POLICY_HASH))
        with self.assertRaises(r.RiskInputError):
            policy(max_position_weight="1.5").validated()
        with self.assertRaises(r.RiskInputError):
            policy(exit_priority=("stop_loss", "stop_loss")).validated()


if __name__ == "__main__":
    argv = [a for a in sys.argv if not a.startswith("--dump=")]
    dump = next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--dump=")), None)
    program = unittest.main(argv=argv, exit=False, verbosity=2)
    if dump:
        Path(dump).write_text(json.dumps(SCENARIO_LOG, indent=1, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    sys.exit(0 if program.result.wasSuccessful() else 1)
