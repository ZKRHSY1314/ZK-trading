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
             limit_state="none", capacity_at=None):
    t = f"{session}T{at}+08:00"
    ct = f"{session}T{capacity_at or at}+08:00"
    trad = k.TradabilityEvidence(symbol, session, trad_status, limit_state, "band", "30.00", "3.00", "not_st", "seasoned", f"{session}T09:15:00+08:00", f"{session}T09:15:00+08:00",
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
        self.assertEqual((back["status"], back["refusals"][0]["code"]), ("refused", "inconsistent_evidence"))
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
        # a later decision while both intents are pending sees the reservations and refuses re-sizing the same symbols
        d2 = E.decide("D2", ctx("2024-03-19"), marks=(mark(A, "10.00", "2024-03-19"), mark(B, "20.00", "2024-03-19")), signals=(signal(A, "2024-03-19"),))
        self.assertEqual(self.entry(d2, A)["reason"], "symbol_pending_intent")
        log("sizing.shared_reservations", E, L)

    def test_execution_gap_recheck_downsizes_or_cancels_without_a_later_close(self):
        E, L = engine("10000.00", pol=policy(max_position_weight="0.30"))           # position room 3000.00 -> 200 shares at 10.01 (est 2002 + 5 + 0.02 = 2007.02)
        d = E.decide("D1", ctx("2024-03-18"), marks=(mark(A, "10.00", "2024-03-18"),), signals=(signal(A, "2024-03-18"),))
        self.assertEqual(self.entry(d, A)["quantity"], 200)
        # gap up to 14.90 (fill 14.92): 200 x 14.92 = 2984.00 + 5.00 + 0.03 = 2989.03 <= 3000 -> still 200; at 14.99 (fill 15.01): 3002.00 > 3000 -> 100
        x = E.execute("D1:buy:SYN_RISK_A", ctx("2024-03-18"), evidence(A, "2024-03-19", "14.99"))
        self.assertEqual(x["status"], "expired")                                     # 15.01 > limit 10.20 -> kernel leaves it unfilled; the only auction of a 1-session intent is used
        self.assertEqual(E.reservations()["reserved_cash"], "0.00")
        self.assertEqual(x["outcome"]["gap"], {"code": "gap_downsized", "from": 200, "to": 100, "observed_price": "14.99", "fill_price_estimate": "15.01", "estimated_cost": "1506.02", "budget": "3000.00"})
        self.assertEqual(x["outcome"]["reasons"][0]["kernel_reasons"][0]["code"], "fill_price_exceeds_limit_price")
        # beyond the whole budget: cancelled, reservation released, nothing posted
        E2, L2 = engine("10000.00", pol=policy(max_position_weight="0.30", max_gap_pct="0.5"))
        E2.decide("D1", ctx("2024-03-18"), marks=(mark(A, "10.00", "2024-03-18"),), signals=(signal(A, "2024-03-18"),))
        x2 = E2.execute("D1:buy:SYN_RISK_A", ctx("2024-03-18"), evidence(A, "2024-03-19", "29.99"))    # fill 30.02 -> one lot 3002.00 + 5 + 0.03 > 3000
        self.assertEqual((x2["status"], x2["reason"]), ("cancelled", "gap_exceeds_budget"))
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
        E, L = engine("100000.00")
        E.decide("D1", ctx("2024-03-18"), marks=(mark(A, "10.00", "2024-03-18"),), signals=(signal(A, "2024-03-18"),))
        part = E.execute("D1:buy:SYN_RISK_A", ctx("2024-03-18"), evidence(A, "2024-03-19", "10.00", at="10:00:00", phase="continuous", capacity=1000, capacity_id="CAP-P"))
        self.assertEqual((part["status"], part["outcome"]["filled_quantity"]), ("partially_filled", 1000))
        self.assertEqual(E.intents()["D1:buy:SYN_RISK_A"]["remaining"], 900)
        self.assertEqual(E.reservations()["reserved_cash"], "20000.00")            # retained for the remainder
        rest = E.execute("D1:buy:SYN_RISK_A", ctx("2024-03-18"), evidence(A, "2024-03-19", "10.00", at="11:00:00", phase="continuous", capacity=5000, capacity_id="CAP-Q", attempt_id="A2"))
        self.assertEqual((rest["status"], rest["outcome"]["filled_quantity"]), ("filled", 900))
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
        bad = E3.execute("D1:buy:SYN_RISK_B", ctx("2024-03-18"), evidence(B, "2024-03-19", "20.00", at="09:30:00", phase="continuous"))   # phase mismatch -> kernel rejects
        self.assertEqual((bad["status"], bad["outcome"]["kernel_status"], bad["outcome"]["committed"]), ("pending", "rejected", False))
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
        E, L = self.held()
        E.decide("D1", ctx("2024-03-19"), marks=(mark(A, "9.00", "2024-03-19"),))
        part = E.execute("D1:sell:SYN_RISK_A", ctx("2024-03-19"), evidence(A, "2024-03-20", "9.00", at="10:00:00", phase="continuous", capacity=600, capacity_id="CAP-X"))
        self.assertEqual((part["status"], part["outcome"]["filled_quantity"], L.positions()), ("partially_filled", 600, {A: 400}))
        self.assertNotIn("cooldown_started_session", part["outcome"])
        self.assertEqual(E.records[-1]["state_summary"]["exit_sessions"], {})
        dup = E.execute("D1:sell:SYN_RISK_A", ctx("2024-03-19"), evidence(A, "2024-03-20", "9.00", at="10:00:00", phase="continuous", capacity=600, capacity_id="CAP-X"))
        self.assertEqual(dup["status"], "duplicate")                                  # replay: no ledger call, no second sale, no cooldown
        self.assertEqual(L.positions(), {A: 400})
        d2 = E.decide("D2", ctx("2024-03-20"), marks=(mark(A, "9.00", "2024-03-20"),), signals=(signal(A, "2024-03-20"),))
        self.assertEqual((self.exit(d2, A)["decision"], self.entry(d2, A)["reason"]), ("exit_pending", "symbol_held"))
        rest = E.execute("D1:sell:SYN_RISK_A", ctx("2024-03-19"), evidence(A, "2024-03-20", "9.00", at="11:00:00", phase="continuous", capacity=5000, capacity_id="CAP-Y", attempt_id="A2"))
        self.assertEqual((rest["status"], rest["outcome"]["cooldown_started_session"], L.positions()), ("filled", "2024-03-20", {}))
        # cooldown 2 sessions from 03-20: 03-21 (1) refused, 03-22 (2) allowed; a non-trading weekend does not count
        self.assertEqual(self.entry(E.decide("D3", ctx("2024-03-21"), marks=(mark(A, "9.00", "2024-03-21"),), signals=(signal(A, "2024-03-21"),)), A)["reason"], "cooldown_active")
        self.assertEqual(self.entry(E.decide("D4", ctx("2024-03-22"), marks=(mark(A, "9.00", "2024-03-22"),), signals=(signal(A, "2024-03-22"),)), A)["decision"], "buy")
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
