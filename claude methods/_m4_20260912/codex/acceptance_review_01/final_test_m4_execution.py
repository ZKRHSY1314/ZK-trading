"""Adversarial synthetic unittest suite for ``backend/app/research/m4_execution.py`` (M4-01).

Run directly with the project interpreter (stdlib unittest, module loaded by file path,
no ``app`` package import, no conftest, no pytest, no SQLite, no network):

    backend/.venv/Scripts/python.exe -B -X utf8 backend/tests/test_m4_execution.py -v

Every fixture is visibly synthetic: ``SYN######`` symbols, ``synthetic=True``, ``syn:`` refs,
and fee/assumption schedules named ``HYPOTHETICAL_FIXTURE_*`` whose numbers are invented for
arithmetic checks and are NOT real historical tariffs.  Expected values are hand-calculated in
the comments next to each assertion and never derived by calling the function under test.

Every result produced by a test is recorded in ``RESULT_LOG`` (name -> result record) so a
runner can dump the rejection, valid non-zero and boundary cases for independent inspection.
"""
from __future__ import annotations

import ast
import dataclasses
import importlib.util
import json
import sys
import unittest
from dataclasses import replace
from decimal import Decimal
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "app" / "research" / "m4_execution.py"
_spec = importlib.util.spec_from_file_location("m4_execution_under_test", MODULE_PATH)
m = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = m
_spec.loader.exec_module(m)

RESULT_LOG: dict[str, dict] = {}

SYM = "SYN000001"
CAL_REF = "syn:calendar-A"
SESSIONS_A = ("2024-03-18", "2024-03-19", "2024-03-20", "2024-03-21", "2024-03-22")  # Mon..Fri; 03-23/24 are not sessions


def calendar(sessions=SESSIONS_A, halted=()):
    return m.SessionCalendar(sessions=tuple(sessions), tz_offset="+08:00", open_time="09:30", close_time="15:00",
                             source_ref=CAL_REF, available_at="2024-01-01T00:00:00+08:00", synthetic=True, halted_sessions=tuple(halted))


def decision(side="buy", session="2024-03-18", decided_at="2024-03-18T16:00:00+08:00", inputs=None):
    return m.Decision(decision_id="DEC-1", symbol=SYM, side=side, decision_session=session, decided_at=decided_at,
                      inputs=inputs or (m.InputAvailability("close_2024-03-18", "2024-03-18T15:05:00+08:00", "syn:bar"),),
                      basis_ref="syn:signal-rule")


def order(side="buy", quantity=2000, limit_price="10.10", submitted_at="2024-03-19T09:00:00+08:00",
          eligible_from="2024-03-19T09:30:00+08:00", expiry_sessions=1, phase="open_auction"):
    return m.Order(order_id="ORD-1", decision_id="DEC-1", symbol=SYM, side=side, quantity=quantity, limit_price=limit_price,
                   submitted_at=submitted_at, eligible_from=eligible_from, expiry_sessions=expiry_sessions, execution_phase=phase)


def instrument(role="stock", symbol=SYM, calendar_ref=CAL_REF):
    return m.Instrument(symbol=symbol, role=role, board="syn_main", listing_evidence_ref="syn:listing-record", calendar_ref=calendar_ref, synthetic=True)


def tradability(session="2024-03-19", status="tradable", limit_state="none", band_state="band", up="11.00", down="9.00",
                st="not_st", listing="seasoned", observed_at="2024-03-19T09:15:00+08:00", available_at="2024-03-19T09:15:00+08:00"):
    return m.TradabilityEvidence(symbol=SYM, session=session, status=status, limit_state=limit_state, band_state=band_state,
                                 limit_up_price=up, limit_down_price=down, st_status=st, listing_state=listing, observed_at=observed_at,
                                 available_at=available_at, source_ref="syn:tradability-feed", synthetic=True)


def price(value="10.00", field="open_auction_print", observed_at="2024-03-19T09:30:00+08:00", available_at="2024-03-19T09:30:00+08:00",
          kind="contemporaneous", assumption_ref=None):
    return m.PriceObservation(symbol=SYM, price=value, field=field, observed_at=observed_at, available_at=available_at,
                              source_ref="syn:auction-feed", kind=kind, synthetic=True, assumption_ref=assumption_ref)


def capacity(quantity=50000, unit="share", observed_at="2024-03-19T09:30:00+08:00", available_at="2024-03-19T09:30:00+08:00",
             consumed=0, kind="contemporaneous", assumption_ref=None, basis="auction_matched_quantity"):
    return m.LiquidityCapacity(symbol=SYM, capacity_id="CAP-1", quantity=quantity, unit=unit, basis=basis, observed_at=observed_at,
                               available_at=available_at, source_ref="syn:auction-feed", kind=kind, synthetic=True,
                               consumed_quantity=consumed, assumption_ref=assumption_ref)


def account(cash="30000.00", inventory=(), as_of="2024-03-19T09:00:00+08:00"):
    return m.AccountState(account_ref="SYN-ACCOUNT-FIXTURE", available_cash=cash, inventory=tuple(inventory), as_of=as_of, synthetic=True)


# HYPOTHETICAL FIXTURE numbers - invented for arithmetic checks, not a real tariff.
def fees(**kw):
    base = dict(schedule_id="HYPOTHETICAL_FIXTURE_FEES_A", version="fixture-1", provenance="hypothetical_fixture",
                source_ref="syn:fee-fixture-A", effective_from="2024-01-01", effective_to="2024-12-31", applies_to_boards=("*",),
                buy_commission_rate="0.0004", sell_commission_rate="0.0004", min_commission="6.00", transfer_fee_rate="0.00002",
                sell_stamp_duty_rate="0.0008")
    base.update(kw)
    return m.FeeSchedule(**base)


def lot_policy(**kw):
    base = dict(policy_id="syn_lot_100", min_buy_quantity=100, buy_increment=100, sell_increment=100,
                odd_lot_sell_rule="whole_odd_remainder_only", max_order_quantity=1_000_000)
    base.update(kw)
    return m.LotPolicy(**base)


def assumptions(slippage="0.002", participation="0.10", tick="0.01", lot=None, settle_after=1, unknown=()):
    return m.ExecutionAssumptions(assumption_id="HYPOTHETICAL_FIXTURE_ASSUMPTIONS_A", provenance="hypothetical_fixture",
                                  source_ref="syn:assumption-fixture-A", slippage_rate=slippage, max_participation_rate=participation,
                                  tick_size=tick, lot_policy=lot or lot_policy(),
                                  settlement_policy=m.SettlementPolicy("syn_T+%d" % settle_after, settle_after),
                                  unknown_state_assumptions=tuple(unknown))


def attempt(executed_at="2024-03-19T09:30:00+08:00", session="2024-03-19", phase="open_auction"):
    return m.ExecutionAttempt(attempt_id="ATT-1", executed_at=executed_at, session=session, phase=phase)


def request(**kw):
    parts = dict(decision=decision(), order=order(), instrument=instrument(), calendar=calendar(), tradability=tradability(),
                 price=price(), account=account(), fee_schedule=fees(), assumptions=assumptions(), attempt=attempt(), capacity=capacity())
    parts.update(kw)
    return m.ExecutionRequest(**parts)


def run(name: str, req) -> "m.ExecutionResult":
    result = m.execute(req)
    RESULT_LOG[name] = result.to_dict()
    return result


def codes(result) -> list[str]:
    return [r["code"] for r in result.reasons]


class KernelCase(unittest.TestCase):
    def assertNoEffect(self, result, status):
        """A rejected/unfilled result must leave nothing behind."""
        self.assertEqual(result.status, status)
        self.assertEqual(result.filled_quantity, 0)
        self.assertEqual(result.cash_delta, Decimal(0))
        self.assertIsNone(result.record["ledger_entry"])
        self.assertFalse(result.record["fill"]["fill_recorded"])
        self.assertEqual(result.record["fill"]["fees"]["total"], "0.00")
        self.assertTrue(result.reasons)

    def assertRejected(self, result, code):
        self.assertNoEffect(result, "rejected")
        self.assertIn(code, codes(result), result.reasons)
        self.assertFalse(result.record["order_live_after_attempt"])

    def assertUnfilled(self, result, code):
        self.assertNoEffect(result, "unfilled")
        self.assertIn(code, codes(result), result.reasons)


# ======================================================================================
class TestContractIdentity(KernelCase):
    def test_cny_capacity_unit_controls_numeric_identity(self):
        """CNY amounts normalize equally; share quantities retain their integer schema."""
        base = request(capacity=capacity(quantity="500000.00", unit="CNY"))
        reference = m.execute(base).to_dict()
        self.assertEqual(reference["status"], "filled")
        for amount in (500000, Decimal("500000.0"), "500000.000"):
            with self.subTest(amount=amount):
                self.assertEqual(m.execute(replace(base, capacity=replace(base.capacity, quantity=amount))).to_dict(), reference)
        shares = request(capacity=capacity(quantity=50000, unit="share"))
        self.assertEqual(m.execute(shares).status, "filled")
        self.assertEqual(m.execute(replace(shares, capacity=replace(shares.capacity, quantity="50000"))).status, "rejected")

    def test_policy_hash_is_stable_and_bound_to_the_result(self):
        self.assertEqual(len(m.POLICY_HASH), 64)
        self.assertEqual(m.POLICY_HASH, m.sha256_text(m.canonical_json(m.POLICY)))
        r = run("identity.positive_buy", request())
        self.assertEqual(r.record["policy_hash"], m.POLICY_HASH)
        self.assertEqual(r.record["contract_version"], "0.1.0-draft")
        self.assertTrue(r.record["review_only"])
        self.assertFalse(r.record["live_trading_enabled"])
        self.assertTrue(r.record["synthetic"])

    def test_result_hash_recomputes_and_is_deterministic(self):
        r1 = m.execute(request())
        r2 = m.execute(request())
        self.assertEqual(r1.result_hash, r2.result_hash)
        self.assertEqual(r1.record["identities"]["input_hash"], r2.record["identities"]["input_hash"])
        body = {k: v for k, v in r1.record.items() if k != "result_hash"}
        self.assertEqual(r1.result_hash, m.sha256_text(m.canonical_json(body)))

    def test_numeric_spelling_does_not_change_identity_but_order_id_does(self):
        a = m.execute(request(order=order(limit_price="10.10"), price=price("10.00")))
        b = m.execute(request(order=order(limit_price=Decimal("10.1")), price=price(Decimal("10"))))
        self.assertEqual(a.record["identities"]["input_hash"], b.record["identities"]["input_hash"])
        c = m.execute(request(order=replace(order(), order_id="ORD-2")))
        self.assertNotEqual(a.record["identities"]["input_hash"], c.record["identities"]["input_hash"])
        self.assertNotEqual(a.result_hash, c.result_hash)

    def test_module_has_no_side_effect_imports_no_clock_and_no_default_rates(self):
        tree = ast.parse(MODULE_PATH.read_text(encoding="utf-8"))
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(a.name.split(".")[0] for a in node.names)
            elif isinstance(node, ast.ImportFrom):
                imported.add((node.module or "").split(".")[0])
        self.assertTrue(imported <= {"hashlib", "json", "dataclasses", "datetime", "decimal", "typing", "__future__"}, imported)
        # no clock, filesystem, environment or process access anywhere in the module body
        calls = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                fn = node.func
                if isinstance(fn, ast.Name):
                    calls.add(fn.id)
                elif isinstance(fn, ast.Attribute):
                    calls.add(fn.attr)
        for forbidden in ("now", "utcnow", "today", "open", "getenv", "environ", "connect", "system", "popen", "run", "exec", "eval", "input"):
            self.assertNotIn(forbidden, calls, forbidden)
        names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)} | {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)}
        for forbidden in ("sqlite3", "socket", "settings", "random", "os", "sys", "pathlib", "subprocess", "urllib"):
            self.assertNotIn(forbidden, names, forbidden)
        source = MODULE_PATH.read_text(encoding="utf-8")
        # every fee rate is a required constructor argument: the kernel carries no tariff numbers
        for f in ("buy_commission_rate", "sell_commission_rate", "min_commission", "transfer_fee_rate", "sell_stamp_duty_rate"):
            self.assertIs(m.FeeSchedule.__dataclass_fields__[f].default, dataclasses.MISSING, f)
        for f in ("slippage_rate", "max_participation_rate", "tick_size"):
            self.assertIs(m.ExecutionAssumptions.__dataclass_fields__[f].default, dataclasses.MISSING, f)
        self.assertNotIn("0.0003", source)
        self.assertNotIn("0.0005", source)


# ======================================================================================
class TestTemporalChain(KernelCase):
    def test_next_session_open_auction_buy_fills_with_exact_hand_calculated_accounting(self):
        r = run("temporal.next_session_positive_buy", request())
        self.assertEqual(r.status, "filled")
        f = r.record["fill"]
        # slippage 0.2% on 10.00 -> 10.02 (tick aligned, rounded up for a buy)
        self.assertEqual(f["fill_price"], "10.02")
        self.assertEqual(f["filled_quantity"], 2000)
        self.assertEqual(f["gross_amount"], "20040.00")              # 2000 x 10.02
        self.assertEqual(f["fees"]["commission"], "8.02")            # 20040 x 0.0004 = 8.016 -> 8.02 (> min 6.00)
        self.assertEqual(f["fees"]["transfer_fee"], "0.40")          # 20040 x 0.00002 = 0.4008 -> 0.40
        self.assertEqual(f["fees"]["stamp_duty"], "0.00")            # buy side: none
        self.assertEqual(f["fees"]["total"], "8.42")
        self.assertEqual(f["slippage_cost_informational"], "40.00")  # 0.02 x 2000, already inside gross
        le = r.record["ledger_entry"]
        self.assertEqual(le["cash_delta"], "-20048.42")               # -(20040.00 + 8.42)
        self.assertEqual(le["cash_after"], "9951.58")                 # 30000.00 - 20048.42
        self.assertEqual(le["quantity_delta"], 2000)
        self.assertEqual(le["sellable_from_session"], "2024-03-20")   # T+1 on exchange sessions
        self.assertTrue(le["slippage_cost_included_in_gross"])
        t = r.record["temporal"]
        self.assertEqual(t["next_session"], "2024-03-19")
        self.assertEqual(t["expiry_session"], "2024-03-19")
        self.assertEqual(t["expires_at"], "2024-03-19T15:00:00+08:00")
        self.assertTrue(t["expires_after_this_session"])
        self.assertFalse(r.record["order_live_after_attempt"])
        self.assertEqual(r.record["evidence"]["evidence_grade"], "contemporaneous")
        self.assertTrue(f["fill_recorded"])

    def test_execution_at_the_decision_close_is_refused(self):
        r = run("temporal.same_close_execution", request(attempt=attempt("2024-03-18T15:00:00+08:00", "2024-03-18", "close_auction"),
                                                          order=order(phase="close_auction")))
        self.assertRejected(r, "execution_before_eligible")

    def test_eligible_point_before_next_session_open_is_refused(self):
        at_close = decision(decided_at="2024-03-18T15:00:00+08:00", inputs=(m.InputAvailability("intraday_snapshot", "2024-03-18T14:59:00+08:00", "syn:snapshot"),))
        r = run("temporal.eligible_at_same_close", request(decision=at_close, order=order(eligible_from="2024-03-18T15:00:00+08:00", submitted_at="2024-03-18T15:00:00+08:00"),
                                                            attempt=attempt("2024-03-18T15:00:00+08:00", "2024-03-18", "close_auction")))
        self.assertRejected(r, "eligible_before_next_session_open")
        r2 = run("temporal.eligible_before_open_next_day", request(order=order(eligible_from="2024-03-19T09:29:59+08:00")))
        self.assertRejected(r2, "eligible_before_next_session_open")

    def test_decision_must_be_after_its_session_close_and_before_next_open(self):
        intraday = (m.InputAvailability("intraday_snapshot", "2024-03-18T14:00:00+08:00", "syn:snapshot"),)
        r = run("temporal.decided_before_close", request(decision=decision(decided_at="2024-03-18T14:59:59+08:00", inputs=intraday)))
        self.assertRejected(r, "decision_before_session_close")
        r2 = run("temporal.decided_at_next_open", request(decision=decision(decided_at="2024-03-19T09:30:00+08:00"),
                                                           order=order(submitted_at="2024-03-19T09:30:00+08:00")))
        self.assertRejected(r2, "decision_after_next_session_open")
        r3 = run("temporal.decided_exactly_at_close", request(decision=decision(decided_at="2024-03-18T15:00:00+08:00", inputs=intraday)))
        self.assertEqual(r3.status, "filled")

    def test_input_available_after_the_decision_is_leakage(self):
        late = (m.InputAvailability("close_2024-03-18", "2024-03-18T15:05:00+08:00", "syn:bar"),
                m.InputAvailability("fundamental_snapshot", "2024-03-18T16:00:01+08:00", "syn:fundamentals"))
        r = run("temporal.input_after_decision", request(decision=decision(inputs=late)))
        self.assertRejected(r, "input_not_available_at_decision")
        self.assertEqual(r.reasons[0]["input"], "fundamental_snapshot")

    def test_submission_ordering(self):
        r = run("temporal.submitted_before_decision", request(order=order(submitted_at="2024-03-18T15:59:59+08:00")))
        self.assertRejected(r, "submitted_before_decision")
        r2 = run("temporal.submitted_after_eligible", request(order=order(submitted_at="2024-03-19T09:30:01+08:00")))
        self.assertRejected(r2, "submitted_after_eligible")

    def test_execution_outside_a_calendar_session_or_phase_is_refused(self):
        r = run("temporal.weekend_execution", request(order=order(expiry_sessions=4), attempt=attempt("2024-03-23T09:30:00+08:00", "2024-03-23")))
        self.assertRejected(r, "execution_outside_session")
        r2 = run("temporal.before_open", request(attempt=attempt("2024-03-19T09:29:00+08:00", "2024-03-19")))
        self.assertRejected(r2, "execution_outside_session")
        r3 = run("temporal.open_auction_at_10am", request(attempt=attempt("2024-03-19T10:00:00+08:00", "2024-03-19", "open_auction")))
        self.assertRejected(r3, "execution_phase_mismatch")
        r4 = run("temporal.phase_differs_from_order", request(attempt=attempt("2024-03-19T10:00:00+08:00", "2024-03-19", "continuous")))
        self.assertRejected(r4, "execution_phase_mismatch")
        r5 = run("temporal.attempt_session_label_wrong", request(attempt=attempt("2024-03-19T09:30:00+08:00", "2024-03-20")))
        self.assertRejected(r5, "attempt_session_mismatch")

    def test_expiry_counts_exchange_sessions_and_a_second_attempt_after_expiry_is_refused(self):
        late = dict(attempt=attempt("2024-03-20T09:30:00+08:00", "2024-03-20"), tradability=tradability(session="2024-03-20",
                    observed_at="2024-03-20T09:15:00+08:00", available_at="2024-03-20T09:15:00+08:00"),
                    price=price(observed_at="2024-03-20T09:30:00+08:00", available_at="2024-03-20T09:30:00+08:00"),
                    capacity=capacity(observed_at="2024-03-20T09:30:00+08:00", available_at="2024-03-20T09:30:00+08:00"))
        r = run("temporal.expired_one_session_order", request(order=order(expiry_sessions=1), **late))
        self.assertRejected(r, "order_expired")
        r2 = run("temporal.two_session_order_second_day", request(order=order(expiry_sessions=2), **late))
        self.assertEqual(r2.status, "filled")
        self.assertEqual(r2.record["temporal"]["sessions_elapsed_in_window"], 2)
        self.assertEqual(r2.record["temporal"]["window_sessions"], ["2024-03-19", "2024-03-20"])

    def test_halted_session_still_counts_toward_expiry(self):
        # exchange session 2024-03-20 is halted; a 2-session order eligible 03-19 still expires at 03-20 15:00, not 03-21
        cal = calendar(halted=("2024-03-20",))
        day3 = dict(calendar=cal, attempt=attempt("2024-03-21T09:30:00+08:00", "2024-03-21"),
                    tradability=tradability(session="2024-03-21", observed_at="2024-03-21T09:15:00+08:00", available_at="2024-03-21T09:15:00+08:00"),
                    price=price(observed_at="2024-03-21T09:30:00+08:00", available_at="2024-03-21T09:30:00+08:00"),
                    capacity=capacity(observed_at="2024-03-21T09:30:00+08:00", available_at="2024-03-21T09:30:00+08:00"))
        r = run("temporal.halted_session_counted_expiry", request(order=order(expiry_sessions=2), **day3))
        self.assertRejected(r, "order_expired")
        self.assertIn("halted ['2024-03-20']", r.reasons[0]["detail"])
        r2 = run("temporal.halted_session_three_session_order", request(order=order(expiry_sessions=3), **day3))
        self.assertEqual(r2.status, "filled")
        self.assertEqual(r2.record["temporal"]["halted_sessions_in_window"], ["2024-03-20"])
        self.assertEqual(r2.record["temporal"]["window_sessions"], ["2024-03-19", "2024-03-20", "2024-03-21"])

    def test_suspension_is_unfilled_and_the_order_stays_live_until_expiry(self):
        r = run("temporal.suspended_first_attempt", request(order=order(expiry_sessions=2), tradability=tradability(status="suspended")))
        self.assertUnfilled(r, "suspended")
        self.assertTrue(r.record["order_live_after_attempt"])
        self.assertEqual(r.record["temporal"]["expires_at"], "2024-03-20T15:00:00+08:00")
        r_last = run("temporal.suspended_on_expiry_session", request(order=order(expiry_sessions=1), tradability=tradability(status="suspended")))
        self.assertUnfilled(r_last, "suspended")
        self.assertFalse(r_last.record["order_live_after_attempt"])
        second = request(order=order(expiry_sessions=2), attempt=attempt("2024-03-20T09:30:00+08:00", "2024-03-20"),
                         tradability=tradability(session="2024-03-20", observed_at="2024-03-20T09:15:00+08:00", available_at="2024-03-20T09:15:00+08:00"),
                         price=price(observed_at="2024-03-20T09:30:00+08:00", available_at="2024-03-20T09:30:00+08:00"),
                         capacity=capacity(observed_at="2024-03-20T09:30:00+08:00", available_at="2024-03-20T09:30:00+08:00"))
        r2 = run("temporal.suspended_then_second_attempt_fills", second)
        self.assertEqual(r2.status, "filled")
        self.assertEqual(r2.record["ledger_entry"]["sellable_from_session"], "2024-03-21")

    def test_changed_future_suffix_cannot_alter_the_earlier_decision(self):
        # a filled buy genuinely consumes its settlement session (T+1 -> 2024-03-20); identity binds the
        # calendar prefix through that session, and only sessions after it are a free suffix
        base = run("temporal.suffix_base", request())
        self.assertEqual(base.record["identities"]["calendar_prefix_last_session"], "2024-03-20")
        self.assertEqual(base.record["temporal"]["consumed_through_session"], "2024-03-20")
        longer = calendar(sessions=SESSIONS_A + ("2024-03-25", "2024-03-26", "2024-03-27"), halted=("2024-03-26",))
        ext = run("temporal.suffix_extended_calendar", request(calendar=longer))
        self.assertEqual(base.result_hash, ext.result_hash)
        self.assertEqual(base.record["identities"]["input_hash"], ext.record["identities"]["input_hash"])
        trimmed = run("temporal.suffix_trimmed_after_settlement", request(calendar=calendar(sessions=SESSIONS_A[:3])))
        self.assertEqual(base.result_hash, trimmed.result_hash)
        # a change inside the consumed prefix (here: the settlement session moves) alters identity AND output
        shifted = calendar(sessions=("2024-03-18", "2024-03-19", "2024-03-21", "2024-03-22"))
        r = run("temporal.prefix_changed", request(calendar=shifted))
        self.assertEqual(r.record["ledger_entry"]["sellable_from_session"], "2024-03-21")
        self.assertNotEqual(base.record["identities"]["input_hash"], r.record["identities"]["input_hash"])
        self.assertNotEqual(base.result_hash, r.result_hash)
        # an unfilled attempt consumes nothing beyond expiry: its prefix ends at the expiry session
        unf = run("temporal.suffix_unfilled_prefix", request(capacity=None))
        self.assertEqual(unf.record["identities"]["calendar_prefix_last_session"], "2024-03-19")
        unf2 = run("temporal.suffix_unfilled_prefix_extended", request(capacity=None, calendar=longer))
        self.assertEqual(unf.result_hash, unf2.result_hash)

    def test_calendar_and_decision_bounds(self):
        r = run("temporal.decision_session_not_in_calendar", request(decision=decision(session="2024-03-17", decided_at="2024-03-17T16:00:00+08:00"),
                                                                       order=order(submitted_at="2024-03-17T16:00:00+08:00")))
        self.assertRejected(r, "decision_session_not_in_calendar")
        r2 = run("temporal.next_session_beyond_calendar", request(decision=decision(session="2024-03-22", decided_at="2024-03-22T16:00:00+08:00"),
                                                                   order=order(submitted_at="2024-03-22T16:00:00+08:00", eligible_from="2024-03-25T09:30:00+08:00")))
        self.assertRejected(r2, "next_session_beyond_calendar")
        r3 = run("temporal.expiry_beyond_calendar", request(order=order(expiry_sessions=10)))
        self.assertRejected(r3, "expiry_beyond_calendar")
        r4 = run("temporal.eligible_from_on_weekend", request(order=order(eligible_from="2024-03-23T09:30:00+08:00", expiry_sessions=1),
                                                               attempt=attempt("2024-03-23T09:30:00+08:00", "2024-03-23")))
        self.assertRejected(r4, "eligible_from_not_in_session")

    def test_declared_later_eligible_point_is_honoured(self):
        later = order(eligible_from="2024-03-20T09:30:00+08:00", expiry_sessions=1)
        r = run("temporal.before_declared_eligible_point", request(order=later))
        self.assertRejected(r, "execution_before_eligible")
        day2 = dict(attempt=attempt("2024-03-20T09:30:00+08:00", "2024-03-20"),
                    tradability=tradability(session="2024-03-20", observed_at="2024-03-20T09:15:00+08:00", available_at="2024-03-20T09:15:00+08:00"),
                    price=price(observed_at="2024-03-20T09:30:00+08:00", available_at="2024-03-20T09:30:00+08:00"),
                    capacity=capacity(observed_at="2024-03-20T09:30:00+08:00", available_at="2024-03-20T09:30:00+08:00"))
        r2 = run("temporal.at_declared_eligible_point", request(order=later, **day2))
        self.assertEqual(r2.status, "filled")
        self.assertEqual(r2.record["temporal"]["eligible_session"], "2024-03-20")
        self.assertEqual(r2.record["temporal"]["expiry_session"], "2024-03-20")

    def test_close_print_can_prove_a_close_auction_fill_but_never_an_opening_fill(self):
        close_px = price("10.30", field="close_auction_print", observed_at="2024-03-19T15:00:00+08:00", available_at="2024-03-19T15:00:00+08:00")
        close_cap = capacity(quantity=30000, basis="close_auction_matched_quantity", observed_at="2024-03-19T15:00:00+08:00", available_at="2024-03-19T15:00:00+08:00")
        r = run("temporal.close_auction_positive", request(order=order(phase="close_auction", limit_price="10.40"), price=close_px, capacity=close_cap,
                                                            attempt=attempt("2024-03-19T15:00:00+08:00", "2024-03-19", "close_auction")))
        self.assertEqual(r.status, "filled")
        self.assertEqual(r.record["fill"]["fill_price"], "10.33")   # 10.30 x 1.002 = 10.3206 -> ceil 10.33
        self.assertEqual(r.record["fill"]["gross_amount"], "20660.00")
        self.assertEqual(r.record["fill"]["fees"]["commission"], "8.26")   # 20660 x 0.0004 = 8.264 -> 8.26
        self.assertEqual(r.record["fill"]["fees"]["transfer_fee"], "0.41")  # 0.4132 -> 0.41
        self.assertEqual(r.record["ledger_entry"]["cash_delta"], "-20668.67")
        r2 = run("temporal.close_print_for_open_attempt", request(price=close_px, capacity=close_cap))
        self.assertRejected(r2, "evidence_observed_after_execution")

    def test_buy_on_the_last_calendar_session_flags_unknown_settlement_session(self):
        last = request(decision=decision(session="2024-03-21", decided_at="2024-03-21T16:00:00+08:00",
                                         inputs=(m.InputAvailability("close_2024-03-21", "2024-03-21T15:05:00+08:00", "syn:bar"),)),
                       order=order(submitted_at="2024-03-22T09:00:00+08:00", eligible_from="2024-03-22T09:30:00+08:00"),
                       tradability=tradability(session="2024-03-22", observed_at="2024-03-22T09:15:00+08:00", available_at="2024-03-22T09:15:00+08:00"),
                       price=price(observed_at="2024-03-22T09:30:00+08:00", available_at="2024-03-22T09:30:00+08:00"),
                       capacity=capacity(observed_at="2024-03-22T09:30:00+08:00", available_at="2024-03-22T09:30:00+08:00"),
                       account=account(as_of="2024-03-22T09:00:00+08:00"), attempt=attempt("2024-03-22T09:30:00+08:00", "2024-03-22"))
        r = run("temporal.buy_last_session_settlement_unknown", last)
        self.assertEqual(r.status, "filled")
        self.assertIsNone(r.record["ledger_entry"]["sellable_from_session"])
        self.assertIn("sellable_session_beyond_calendar", r.record["flags"])

    def test_duplicated_or_unordered_temporal_evidence_is_invalid(self):
        dup = (m.InputAvailability("close", "2024-03-18T15:05:00+08:00", "syn:bar"), m.InputAvailability("close", "2024-03-18T15:05:00+08:00", "syn:bar"))
        r = run("temporal.duplicate_inputs", request(decision=decision(inputs=dup)))
        self.assertRejected(r, "invalid_input")
        self.assertIn("duplicate decision input", r.reasons[0]["detail"])
        r2 = run("temporal.unordered_calendar", request(calendar=calendar(sessions=("2024-03-19", "2024-03-18", "2024-03-20"))))
        self.assertRejected(r2, "invalid_input")
        r3 = run("temporal.duplicate_calendar_session", request(calendar=calendar(sessions=("2024-03-18", "2024-03-19", "2024-03-19"))))
        self.assertRejected(r3, "invalid_input")
        r4 = run("temporal.naive_timestamp", request(attempt=attempt("2024-03-19T09:30:00", "2024-03-19")))
        self.assertRejected(r4, "invalid_input")
        self.assertIn("timezone-aware", r4.reasons[0]["detail"])


# ======================================================================================
class TestEvidenceTiming(KernelCase):
    def test_price_available_only_after_execution_cannot_prove_the_fill(self):
        r = run("evidence.price_available_after_execution", request(price=price(available_at="2024-03-19T15:05:00+08:00")))
        self.assertRejected(r, "evidence_available_after_execution")
        self.assertEqual(r.reasons[0]["evidence"], "price")

    def test_full_day_close_cannot_decide_an_opening_fill(self):
        r = run("evidence.close_used_for_open", request(price=price("10.30", field="close", observed_at="2024-03-19T15:00:00+08:00",
                                                                     available_at="2024-03-19T15:00:00+08:00")))
        self.assertRejected(r, "evidence_observed_after_execution")
        r2 = run("evidence.full_day_amount_capacity_for_open", request(capacity=capacity(quantity="5000000.00", unit="CNY", basis="full_day_amount",
                                                                                          observed_at="2024-03-19T15:00:00+08:00",
                                                                                          available_at="2024-03-19T15:00:00+08:00")))
        self.assertRejected(r2, "evidence_observed_after_execution")
        self.assertEqual(r2.reasons[0]["evidence"], "capacity")

    def test_predeclared_assumption_is_allowed_only_with_a_reference_and_is_flagged(self):
        r = run("evidence.assumed_open_print", request(price=price(kind="predeclared_assumption", available_at="2024-03-19T15:05:00+08:00",
                                                                    assumption_ref="syn:assume-daily-open-equals-auction-print")))
        self.assertEqual(r.status, "filled")
        self.assertEqual(r.record["evidence"]["evidence_grade"], "assumed")
        self.assertEqual(r.record["evidence"]["assumptions_used"], ["price:syn:assume-daily-open-equals-auction-print"])
        r2 = run("evidence.assumption_without_ref", request(price=price(kind="predeclared_assumption", available_at="2024-03-19T15:05:00+08:00")))
        self.assertRejected(r2, "evidence_without_provenance")
        r3 = run("evidence.contemporaneous_with_ref", request(price=price(assumption_ref="syn:x")))
        self.assertRejected(r3, "invalid_input")

    def test_missing_capacity_evidence_is_unfilled_not_an_invented_fill(self):
        r = run("evidence.capacity_unproven", request(capacity=None))
        self.assertUnfilled(r, "capacity_unproven")
        self.assertFalse(r.record["order_live_after_attempt"])  # 1-session order expires with this session

    def test_evidence_from_another_session_or_after_the_account_snapshot_is_mismatched(self):
        r = run("evidence.price_from_previous_session", request(price=price(observed_at="2024-03-18T15:00:00+08:00", available_at="2024-03-18T15:00:00+08:00")))
        self.assertRejected(r, "evidence_session_mismatch")
        r2 = run("evidence.tradability_other_session", request(tradability=tradability(session="2024-03-18", observed_at="2024-03-18T09:15:00+08:00",
                                                                                          available_at="2024-03-18T09:15:00+08:00")))
        self.assertRejected(r2, "evidence_session_mismatch")
        r3 = run("evidence.account_after_execution", request(account=account(as_of="2024-03-19T09:30:01+08:00")))
        self.assertRejected(r3, "account_state_after_execution")
        r4 = run("evidence.tradability_available_late", request(tradability=tradability(available_at="2024-03-19T09:30:01+08:00")))
        self.assertRejected(r4, "evidence_available_after_execution")

    def test_declared_symbol_without_provenance_is_not_evidence(self):
        r = run("evidence.no_source_ref", request(price=replace(price(), source_ref="")))
        self.assertRejected(r, "evidence_without_provenance")
        r2 = run("evidence.no_listing_ref", request(instrument=replace(instrument(), listing_evidence_ref="")))
        self.assertRejected(r2, "evidence_without_provenance")

    def test_unknown_states_are_rejected_unless_explicitly_assumed(self):
        r = run("evidence.unknown_limit_state", request(tradability=tradability(limit_state="unknown")))
        self.assertRejected(r, "unknown_state")
        self.assertEqual(r.reasons[0]["field"], "limit_state")
        r2 = run("evidence.unknown_st", request(tradability=tradability(st="unknown")))
        self.assertRejected(r2, "unknown_state")
        r3 = run("evidence.unknown_listing", request(tradability=tradability(listing="unknown")))
        self.assertRejected(r3, "unknown_state")
        r4 = run("evidence.tradability_unknown", request(tradability=tradability(status="unknown")))
        self.assertRejected(r4, "tradability_unknown")
        assumed = assumptions(unknown=(("st_status", "not_st"), ("limit_state", "none")))
        r5 = run("evidence.unknown_states_assumed", request(tradability=tradability(st="unknown", limit_state="unknown"), assumptions=assumed))
        self.assertEqual(r5.status, "filled")
        self.assertEqual(r5.record["evidence"]["assumed_states"], {"limit_state": "none", "st_status": "not_st"})
        self.assertEqual(r5.record["evidence"]["evidence_grade"], "assumed")
        with self.assertRaises(m.ExecutionInputError):
            assumptions(unknown=(("st_status", "unknown"),)).validated()


# ======================================================================================
class TestIdentityMatching(KernelCase):
    def test_benchmark_or_index_role_is_never_executed(self):
        r = run("identity.benchmark_role", request(instrument=instrument(role="benchmark")))
        self.assertRejected(r, "non_tradable_role")
        r2 = run("identity.index_role", request(instrument=instrument(role="index")))
        self.assertRejected(r2, "non_tradable_role")

    def test_symbol_calendar_side_and_decision_must_match(self):
        r = run("identity.symbol_mismatch", request(instrument=instrument(symbol="SYN000002")))
        self.assertRejected(r, "symbol_mismatch")
        r2 = run("identity.calendar_mismatch", request(instrument=instrument(calendar_ref="syn:calendar-B")))
        self.assertRejected(r2, "calendar_mismatch")
        r3 = run("identity.side_mismatch", request(decision=decision(side="sell")))
        self.assertRejected(r3, "side_mismatch")
        r4 = run("identity.decision_id_mismatch", request(order=replace(order(), decision_id="DEC-9")))
        self.assertRejected(r4, "decision_id_mismatch")


# ======================================================================================
class TestLimitsAndPrice(KernelCase):
    settled = (m.InventoryLot(1000, "2024-03-18"),)

    def test_side_specific_limit_states(self):
        r = run("limit.limit_up_buy", request(tradability=tradability(limit_state="limit_up"), price=price("11.00")))
        self.assertUnfilled(r, "limit_up_no_buy_fill")
        sell = request(decision=decision(side="sell"), order=order(side="sell", quantity=500, limit_price="10.00"),
                       tradability=tradability(limit_state="limit_up"), price=price("11.00"), account=account(inventory=self.settled))
        r2 = run("limit.limit_up_sell_fills", sell)
        self.assertEqual(r2.status, "filled")
        self.assertEqual(r2.record["fill"]["fill_price"], "10.97")   # 11.00 x 0.998 = 10.978 -> floor tick 10.97
        r3 = run("limit.limit_down_sell", request(decision=decision(side="sell"), order=order(side="sell", quantity=500, limit_price="9.00"),
                                                   tradability=tradability(limit_state="limit_down"), price=price("9.00"), account=account(inventory=self.settled)))
        self.assertUnfilled(r3, "limit_down_no_sell_fill")
        r4 = run("limit.limit_down_buy_fills", request(tradability=tradability(limit_state="limit_down"), price=price("9.00")))
        self.assertEqual(r4.status, "filled")
        self.assertEqual(r4.record["fill"]["fill_price"], "9.02")     # 9.00 x 1.002 = 9.018 -> ceil tick 9.02

    def test_slippage_rounds_to_the_tick_against_the_trader(self):
        r = run("price.buy_rounds_up", request(price=price("10.03")))
        self.assertEqual(r.record["fill"]["fill_price"], "10.06")     # 10.03 x 1.002 = 10.05006 -> ceil 10.06
        self.assertEqual(r.record["fill"]["gross_amount"], "20120.00")
        self.assertEqual(r.record["fill"]["slippage_cost_informational"], "60.00")
        r2 = run("price.sell_rounds_down", request(decision=decision(side="sell"), order=order(side="sell", quantity=500, limit_price="9.90"),
                                                    price=price("10.03"), account=account(inventory=self.settled)))
        self.assertEqual(r2.record["fill"]["fill_price"], "10.00")    # 10.03 x 0.998 = 10.00994 -> floor 10.00

    def test_slipped_price_is_capped_at_the_band_edge_and_flagged(self):
        r = run("price.slippage_capped_at_band", request(price=price("10.99"), order=order(limit_price="11.00")))
        self.assertEqual(r.status, "filled")
        self.assertEqual(r.record["fill"]["fill_price"], "11.00")     # 10.99 x 1.002 = 11.01198 -> 11.02 > band 11.00 -> 11.00
        self.assertIn("slippage_capped_at_band", r.record["flags"])

    def test_limit_price_interaction(self):
        r = run("price.fill_exceeds_limit", request(order=order(limit_price="10.01")))
        self.assertUnfilled(r, "fill_price_exceeds_limit_price")
        self.assertEqual(r.reasons[0]["fill_price"], "10.02")
        r2 = run("price.sell_below_limit", request(decision=decision(side="sell"), order=order(side="sell", quantity=500, limit_price="10.00"),
                                                    price=price("10.00"), account=account(inventory=self.settled)))
        self.assertUnfilled(r2, "fill_price_below_limit_price")      # 10.00 x 0.998 -> 9.98 < 10.00
        r3 = run("price.limit_outside_band", request(order=order(limit_price="11.50")))
        self.assertRejected(r3, "limit_price_outside_band")
        r4 = run("price.not_tick_aligned", request(price=price("10.005")))
        self.assertRejected(r4, "price_not_tick_aligned")
        r5 = run("price.limit_not_tick_aligned", request(order=order(limit_price="10.105")))
        self.assertRejected(r5, "price_not_tick_aligned")

    def test_band_declarations(self):
        r = run("price.band_prices_missing", request(tradability=tradability(up=None, down=None)))
        self.assertRejected(r, "band_prices_missing")
        r2 = run("price.band_inverted", request(tradability=tradability(up="9.00", down="11.00")))
        self.assertRejected(r2, "band_prices_invalid")
        r3 = run("price.no_band_new_listing", request(tradability=tradability(band_state="no_band", up=None, down=None, listing="new_listing")))
        self.assertEqual(r3.status, "filled")
        self.assertEqual(r3.record["flags"], ["new_listing", "no_price_band"])
        r4 = run("price.st_flagged", request(tradability=tradability(st="st")))
        self.assertIn("st_security", r4.record["flags"])


# ======================================================================================
class TestQuantityAndCapacity(KernelCase):
    def test_lot_policy_is_enforced_not_silently_rounded(self):
        r = run("quantity.buy_150_not_a_lot", request(order=order(quantity=150)))
        self.assertRejected(r, "quantity_not_in_lot_policy")
        r2 = run("quantity.buy_above_max", request(order=order(quantity=2_000_000), account=account(cash="100000000.00")))
        self.assertRejected(r2, "quantity_not_in_lot_policy")
        star_like = lot_policy(policy_id="syn_lot_min200_step1", min_buy_quantity=200, buy_increment=1, sell_increment=1, odd_lot_sell_rule="any")
        r3 = run("quantity.declared_alternative_lot_policy", request(order=order(quantity=257), assumptions=assumptions(lot=star_like)))
        self.assertEqual(r3.status, "filled")
        self.assertEqual(r3.record["fill"]["gross_amount"], "2575.14")   # 257 x 10.02

    def test_partial_fill_from_participation_capacity_with_lot_rounding(self):
        r = run("quantity.partial_capacity", request(order=order(quantity=2000, expiry_sessions=2), capacity=capacity(quantity=12345)))
        self.assertEqual(r.status, "partially_filled")
        f = r.record["fill"]
        self.assertEqual(f["capacity"]["allowance_quantity"], 1234)     # floor(12345 x 0.10)
        self.assertEqual(f["filled_quantity"], 1200)                     # rounded down to the 100 increment
        self.assertEqual(f["remaining_quantity"], 800)
        self.assertEqual(f["gross_amount"], "12024.00")                  # 1200 x 10.02
        self.assertEqual(f["fees"]["commission"], "6.00")                # 12024 x 0.0004 = 4.8096 -> 4.81 < min 6.00
        self.assertEqual(f["fees"]["transfer_fee"], "0.24")              # 0.24048 -> 0.24
        self.assertEqual(r.record["ledger_entry"]["cash_delta"], "-12030.24")
        self.assertTrue(r.record["order_live_after_attempt"])            # 800 remain, order expires next session

    def test_cumulative_capacity_contract(self):
        rich = account(cash="100000.00")
        first = run("quantity.cumulative_first", request(order=order(quantity=3000), account=rich))
        self.assertEqual(first.status, "filled")
        self.assertEqual(first.record["fill"]["gross_amount"], "30060.00")   # 3000 x 10.02
        self.assertEqual(first.record["fill"]["capacity"]["consumed_after"], 3000)
        second = run("quantity.cumulative_second_partial", request(order=replace(order(quantity=3000), order_id="ORD-2"), capacity=capacity(consumed=3000), account=rich))
        self.assertEqual(second.status, "partially_filled")
        self.assertEqual(second.filled_quantity, 2000)                   # allowance 5000 - consumed 3000
        self.assertEqual(second.record["fill"]["capacity"]["remaining_allowance_after"], 0)
        third = run("quantity.cumulative_exhausted", request(order=replace(order(quantity=100), order_id="ORD-3"), capacity=capacity(consumed=5000), account=rich))
        self.assertUnfilled(third, "capacity_exhausted")
        small = run("quantity.capacity_below_min_lot", request(capacity=capacity(quantity=990)))   # allowance 99 -> 0 lots
        self.assertUnfilled(small, "capacity_below_minimum_lot")

    def test_amount_capacity_is_converted_at_the_fill_price(self):
        r = run("quantity.cny_capacity", request(capacity=capacity(quantity="100000.00", unit="CNY", basis="auction_matched_amount")))
        self.assertEqual(r.status, "partially_filled")
        self.assertEqual(r.record["fill"]["capacity"]["allowance_quantity"], 998)   # 100000 x 0.10 / 10.02 = 998.00... -> 998
        self.assertEqual(r.filled_quantity, 900)


# ======================================================================================
class TestCashAndFees(KernelCase):
    def test_buy_affordability_includes_minimum_commission_and_transfer_fee(self):
        r = run("cash.short_by_one_cent", request(account=account(cash="20048.41")))
        self.assertRejected(r, "insufficient_cash")
        self.assertEqual(r.reasons[0]["required"], "20048.42")
        self.assertEqual(r.reasons[0]["shortfall"], "0.01")
        r2 = run("cash.gross_only_is_not_enough", request(account=account(cash="20040.00")))
        self.assertRejected(r2, "insufficient_cash")
        r3 = run("cash.exact_cash", request(account=account(cash="20048.42")))
        self.assertEqual(r3.status, "filled")
        self.assertEqual(r3.record["ledger_entry"]["cash_after"], "0.00")

    def test_minimum_commission_binds_on_a_small_buy(self):
        r = run("cash.small_buy_min_commission", request(order=order(quantity=500), account=account(cash="5016.10")))
        self.assertEqual(r.status, "filled")
        f = r.record["fill"]
        self.assertEqual(f["gross_amount"], "5010.00")        # 500 x 10.02
        self.assertEqual(f["fees"]["commission"], "6.00")     # 5010 x 0.0004 = 2.004 -> 2.00 < 6.00 minimum
        self.assertEqual(f["fees"]["transfer_fee"], "0.10")   # 0.1002 -> 0.10
        self.assertEqual(r.record["ledger_entry"]["cash_delta"], "-5016.10")
        r2 = run("cash.small_buy_short", request(order=order(quantity=500), account=account(cash="5016.09")))
        self.assertRejected(r2, "insufficient_cash")

    def test_sell_with_exact_fee_and_cash_results(self):
        req = request(decision=decision(side="sell", session="2024-03-19", decided_at="2024-03-19T16:00:00+08:00",
                                        inputs=(m.InputAvailability("close_2024-03-19", "2024-03-19T15:05:00+08:00", "syn:bar"),)),
                      order=order(side="sell", quantity=1000, limit_price="10.40", submitted_at="2024-03-20T09:00:00+08:00",
                                  eligible_from="2024-03-20T09:30:00+08:00", phase="continuous"),
                      tradability=tradability(session="2024-03-20", observed_at="2024-03-20T10:14:00+08:00", available_at="2024-03-20T10:14:00+08:00"),
                      price=price("10.50", field="last_trade", observed_at="2024-03-20T10:15:00+08:00", available_at="2024-03-20T10:15:00+08:00"),
                      capacity=capacity(quantity=40000, basis="queue_depth_at_touch", observed_at="2024-03-20T10:15:00+08:00", available_at="2024-03-20T10:15:00+08:00"),
                      account=account(cash="100.00", inventory=(m.InventoryLot(2000, "2024-03-19"),), as_of="2024-03-20T09:00:00+08:00"),
                      attempt=attempt("2024-03-20T10:15:00+08:00", "2024-03-20", "continuous"))
        r = run("cash.sell_positive", req)
        self.assertEqual(r.status, "filled")
        f = r.record["fill"]
        self.assertEqual(f["fill_price"], "10.47")             # 10.50 x 0.998 = 10.479 -> floor 10.47
        self.assertEqual(f["gross_amount"], "10470.00")
        self.assertEqual(f["fees"]["commission"], "6.00")      # 4.188 -> 4.19 < 6.00 minimum
        self.assertEqual(f["fees"]["transfer_fee"], "0.21")    # 0.2094 -> 0.21
        self.assertEqual(f["fees"]["stamp_duty"], "8.38")      # 10470 x 0.0008 = 8.376 -> 8.38
        self.assertEqual(f["fees"]["total"], "14.59")
        le = r.record["ledger_entry"]
        self.assertEqual(le["cash_delta"], "10455.41")         # 10470.00 - 14.59
        self.assertEqual(le["cash_after"], "10555.41")
        self.assertEqual(le["quantity_delta"], -1000)
        self.assertEqual(le["settled_sellable_after"], 1000)
        self.assertIsNone(le["sellable_from_session"])
        self.assertEqual(r.record["inventory"], {"held_total": 2000, "settled_sellable": 2000, "unsettled": 0, "settlement_policy": "syn_T+1",
                                                 "sellable_after_sessions": 1, "lot_policy": "syn_lot_100", "available_cash_before": "100.00"})

    def test_fee_schedule_applicability_and_provenance(self):
        r = run("cash.fees_not_yet_effective", request(fee_schedule=fees(effective_from="2024-03-20")))
        self.assertRejected(r, "fee_schedule_not_applicable")
        r2 = run("cash.fees_expired", request(fee_schedule=fees(effective_to="2024-03-18")))
        self.assertRejected(r2, "fee_schedule_not_applicable")
        r3 = run("cash.fees_wrong_board", request(fee_schedule=fees(applies_to_boards=("syn_star",))))
        self.assertRejected(r3, "fee_schedule_not_applicable")
        r4 = run("cash.fees_sourced_without_verification", request(fee_schedule=fees(provenance="sourced_verified")))
        self.assertRejected(r4, "evidence_without_provenance")
        with self.assertRaises(m.ExecutionInputError):
            fees(provenance="real_current_tariff").validated()

    def test_fees_larger_than_proceeds_cannot_push_cash_negative(self):
        tiny = dict(decision=decision(side="sell"), order=order(side="sell", quantity=100, limit_price="0.01"),
                    tradability=tradability(up="0.10", down="0.01"), price=price("0.05"), capacity=capacity(quantity=10000))
        r = run("cash.sell_fees_exceed_proceeds_negative", request(account=account(cash="1.00", inventory=(m.InventoryLot(100, "2024-03-18"),)), **tiny))
        self.assertRejected(r, "negative_cash_after_fees")      # gross 100 x 0.04 = 4.00; fees 6.00 + 0.00 + 0.00 -> proceeds -2.00
        r2 = run("cash.sell_fees_exceed_proceeds_covered", request(account=account(cash="2.00", inventory=(m.InventoryLot(100, "2024-03-18"),)), **tiny))
        self.assertEqual(r2.status, "filled")
        self.assertEqual(r2.record["ledger_entry"]["cash_delta"], "-2.00")
        self.assertEqual(r2.record["ledger_entry"]["cash_after"], "0.00")

    def test_rejected_and_unfilled_never_carry_cash_flow(self):
        for name, req in (("noeffect.rejected", request(account=account(cash="1.00"))), ("noeffect.unfilled", request(capacity=None))):
            r = run(name, req)
            self.assertIn(r.status, ("rejected", "unfilled"))
            self.assertEqual(r.record["fill"], m._empty_fill())
            self.assertIsNone(r.record["ledger_entry"])


# ======================================================================================
class TestSettlement(KernelCase):
    def sell_req(self, quantity, inventory, session="2024-03-19", policy_after=1, lot=None):
        """A prior-close (2024-03-18) sell decision attempted at ``session`` open; 3-session expiry."""
        return request(decision=decision(side="sell"),
                       order=order(side="sell", quantity=quantity, limit_price="9.90", expiry_sessions=3),
                       tradability=tradability(session=session, observed_at=f"{session}T09:15:00+08:00", available_at=f"{session}T09:15:00+08:00"),
                       price=price(observed_at=f"{session}T09:30:00+08:00", available_at=f"{session}T09:30:00+08:00"),
                       capacity=capacity(observed_at=f"{session}T09:30:00+08:00", available_at=f"{session}T09:30:00+08:00"),
                       account=account(cash="0.00", inventory=inventory, as_of=f"{session}T09:00:00+08:00"),
                       attempt=attempt(f"{session}T09:30:00+08:00", session), assumptions=assumptions(settle_after=policy_after, lot=lot))

    def test_same_session_inventory_is_not_sellable_under_t_plus_one(self):
        r = run("settle.same_session_sell", self.sell_req(1000, (m.InventoryLot(2000, "2024-03-19"),)))
        self.assertRejected(r, "insufficient_settled_inventory")
        self.assertEqual(r.reasons[0]["settled_sellable"], 0)
        self.assertEqual(r.reasons[0]["unsettled"], 2000)

    def test_original_settled_inventory_remains_sellable_next_to_unsettled_inventory(self):
        mixed = (m.InventoryLot(1000, "2024-03-18"), m.InventoryLot(2000, "2024-03-19"))
        r = run("settle.settled_lot_sells", self.sell_req(1000, mixed))
        self.assertEqual(r.status, "filled")
        self.assertEqual(r.record["inventory"]["settled_sellable"], 1000)
        self.assertEqual(r.record["inventory"]["unsettled"], 2000)
        self.assertEqual(r.record["ledger_entry"]["settled_sellable_after"], 0)
        r2 = run("settle.over_settled", self.sell_req(1500, mixed))
        self.assertRejected(r2, "insufficient_settled_inventory")
        r3 = run("settle.next_session_all_settled", self.sell_req(3000, mixed, session="2024-03-20"))
        self.assertEqual(r3.status, "filled")

    def test_declared_t_plus_zero_policy_allows_same_session_sale(self):
        r = run("settle.declared_t0", self.sell_req(1000, (m.InventoryLot(2000, "2024-03-19"),), policy_after=0))
        self.assertEqual(r.status, "filled")
        self.assertEqual(r.record["inventory"]["settlement_policy"], "syn_T+0")

    def test_halted_session_counts_toward_settlement(self):
        buy = run("settle.buy_before_halt", request(calendar=calendar(halted=("2024-03-20",))))
        self.assertEqual(buy.record["ledger_entry"]["sellable_from_session"], "2024-03-20")
        req = self.sell_req(1000, (m.InventoryLot(1000, "2024-03-19"),), session="2024-03-21")
        req = replace(req, calendar=calendar(halted=("2024-03-20",)))
        r = run("settle.sell_after_halted_session", req)
        self.assertEqual(r.status, "filled")
        with self.assertRaises(m.ExecutionInputError):
            m.SettlementPolicy("bad", 1, counts_halted_sessions=False).validated()

    def test_odd_lot_rules_are_declared(self):
        inv = (m.InventoryLot(1000, "2024-03-18"), m.InventoryLot(150, "2024-03-18"))   # settled 1150 -> odd remainder 50
        r = run("settle.odd_remainder_whole", self.sell_req(150, inv))
        self.assertEqual(r.status, "filled")
        r2 = run("settle.odd_partial_remainder", self.sell_req(120, inv))
        self.assertRejected(r2, "odd_lot_rule_violation")
        r3 = run("settle.odd_forbidden", self.sell_req(150, inv, lot=lot_policy(odd_lot_sell_rule="forbidden")))
        self.assertRejected(r3, "odd_lot_rule_violation")
        r4 = run("settle.odd_any", self.sell_req(120, inv, lot=lot_policy(odd_lot_sell_rule="any")))
        self.assertEqual(r4.status, "filled")


# ======================================================================================
class TestInvalidInputs(KernelCase):
    def check(self, name, req, fragment):
        r = run(name, req)
        self.assertRejected(r, "invalid_input")
        self.assertIn(fragment, r.reasons[0]["detail"], r.reasons[0]["detail"])
        self.assertIsNone(r.record["identities"]["input_hash"])

    def test_nan_inf_zero_negative_and_float_inputs(self):
        self.check("invalid.nan_price", request(price=price(float("nan"))), "not float")
        self.check("invalid.nan_string_price", request(price=price("NaN")), "finite")
        self.check("invalid.inf_cash", request(account=account(cash="Infinity")), "finite")
        self.check("invalid.zero_quantity", request(order=order(quantity=0)), "within [1")
        self.check("invalid.negative_quantity", request(order=order(quantity=-100)), "within [1")
        self.check("invalid.negative_cash", request(account=account(cash="-1.00")), ">= 0")
        self.check("invalid.float_limit_price", request(order=order(limit_price=10.1)), "not float")
        self.check("invalid.zero_price", request(price=price("0")), "> 0")
        self.check("invalid.bool_quantity", request(order=order(quantity=True)), "must be int")
        self.check("invalid.cash_three_decimals", request(account=account(cash="100.005")), "2 decimals")
        self.check("invalid.negative_rate", request(fee_schedule=fees(buy_commission_rate="-0.0001")), "within [0")
        self.check("invalid.rate_too_large", request(fee_schedule=fees(sell_stamp_duty_rate="0.9")), "within [0")
        self.check("invalid.zero_tick", request(assumptions=assumptions(tick="0")), "> 0")
        self.check("invalid.slippage_too_large", request(assumptions=assumptions(slippage="0.5")), "within [0")
        self.check("invalid.negative_consumed", request(capacity=capacity(consumed=-1)), "within [0")
        self.check("invalid.bad_side", request(order=replace(order(), side="short")), "one of")
        self.check("invalid.bad_currency", request(fee_schedule=fees(currency="USD")), "CNY")
        self.check("invalid.wrong_type", request(price="10.00"), "unsupported type")


# ======================================================================================
class TestStatusesAndFlags(KernelCase):
    def test_statuses_are_distinct_and_only_fills_record_effects(self):
        seen = {}
        seen["filled"] = run("status.filled", request())
        seen["partially_filled"] = run("status.partial", request(capacity=capacity(quantity=12345)))
        seen["unfilled"] = run("status.unfilled", request(tradability=tradability(status="suspended")))
        seen["rejected"] = run("status.rejected", request(instrument=instrument(role="benchmark")))
        self.assertEqual(sorted(seen), sorted(m.STATUSES))
        for status, r in seen.items():
            self.assertEqual(r.status, status)
            self.assertEqual(r.record["fill"]["fill_recorded"], status in ("filled", "partially_filled"))
            self.assertEqual(r.record["ledger_entry"] is not None, status in ("filled", "partially_filled"))
        self.assertEqual(seen["filled"].record["reasons"], [])
        for r in (seen["unfilled"], seen["rejected"]):
            self.assertEqual(r.record["fill"]["filled_quantity"], 0)

    def test_synthetic_flag_propagates_and_review_flags_are_fixed(self):
        r = run("flags.synthetic", request())
        self.assertTrue(r.record["synthetic"])
        real_format = request(instrument=replace(instrument(), synthetic=False), calendar=replace(calendar(), synthetic=False),
                              tradability=replace(tradability(), synthetic=False), price=replace(price(), synthetic=False),
                              account=replace(account(), synthetic=False), capacity=replace(capacity(), synthetic=False))
        r2 = run("flags.fixture_only_real_format", real_format)   # in-memory format check only; nothing here is a real market fact
        self.assertFalse(r2.record["synthetic"])
        self.assertTrue(r2.record["review_only"])
        self.assertFalse(r2.record["live_trading_enabled"])
        self.assertEqual(m.POLICY["flags"], {"review_only": True, "live_trading_enabled": False, "synthetic": "true if any input is synthetic"})

    def test_inputs_are_never_mutated_and_domain_rejections_keep_their_input_identity(self):
        req = request(account=account(cash="1.00"))
        before = m.canonical_json(m._record(req))
        r = run("flags.rejected_keeps_input_hash", req)
        self.assertRejected(r, "insufficient_cash")
        self.assertEqual(len(r.record["identities"]["input_hash"]), 64)
        self.assertEqual(m.canonical_json(m._record(req)), before)
        r2 = run("flags.observed_price_outside_band", request(price=price("12.00"), order=order(limit_price="11.00")))
        self.assertRejected(r2, "band_prices_invalid")
        r3 = run("flags.quantity_overflow", request(order=order(quantity=10**13)))
        self.assertRejected(r3, "invalid_input")

    def test_reason_codes_are_declared_in_the_policy(self):
        for r in RESULT_LOG.values():
            for reason in r["reasons"]:
                self.assertIn(reason["code"], set(m.REJECT_CODES) | set(m.UNFILLED_CODES), reason)
                if r["status"] == "rejected":
                    self.assertIn(reason["code"], m.REJECT_CODES)
                if r["status"] == "unfilled":
                    self.assertIn(reason["code"], m.UNFILLED_CODES)


# ======================================================================================
class TestCodexWorkingReview01(KernelCase):
    """Re-expression of the six findings in codex/M4_01_WORKING_REVIEW_01.md (sha256 6fb03268...) with the
    same synthetic values Codex used in codex/probe_m4_working_01.py (a 100-share buy at 10.00 with a
    hypothetical 5.00 minimum commission and 0.00001 transfer fee -> cash -1005.01, zero slippage,
    participation 1).  Each expectation is stated from the contract, not read off the implementation."""

    CX = "SYN_CODEX_01"
    CX_SESSIONS = ("2024-03-18", "2024-03-19", "2024-03-20", "2024-03-21")
    T = "2024-03-19T09:30:00+08:00"
    T10 = "2024-03-19T10:00:00+08:00"
    T11 = "2024-03-19T11:00:00+08:00"

    def cx_calendar(self, sessions=None, available_at="2024-01-01T00:00:00+08:00"):
        return m.SessionCalendar(sessions or self.CX_SESSIONS, "+08:00", "09:30", "15:00", "syn:calendar", available_at, True)

    def cx_request(self, **kw):
        S, T = self.CX, self.T
        parts = dict(
            decision=m.Decision("D", S, "buy", "2024-03-18", "2024-03-18T16:00:00+08:00", (m.InputAvailability("prior_close", "2024-03-18T15:05:00+08:00", "syn:prior_close"),), "syn:rule"),
            order=m.Order("O", "D", S, "buy", 100, "10.00", "2024-03-19T09:00:00+08:00", T, 1, "open_auction"),
            instrument=m.Instrument(S, "stock", "syn_main", "syn:listing", "syn:calendar", True),
            calendar=self.cx_calendar(),
            tradability=m.TradabilityEvidence(S, "2024-03-19", "tradable", "none", "band", "11.00", "9.00", "not_st", "seasoned", T, T, "syn:tradable", True),
            price=m.PriceObservation(S, "10.00", "open_auction_print", T, T, "syn:price", "contemporaneous", True),
            capacity=m.LiquidityCapacity(S, "C", 1000, "share", "auction_matched_quantity", T, T, "syn:capacity", "contemporaneous", True),
            account=m.AccountState("SYN_CODEX_ACCOUNT", "10000.00", (), "2024-03-19T09:00:00+08:00", True),
            fee_schedule=m.FeeSchedule("HYPOTHETICAL_CODEX", "1", "hypothetical_fixture", "syn:fees", "2024-01-01", None, ("syn_main",), "0.0003", "0.0003", "5.00", "0.00001", "0.0005"),
            assumptions=m.ExecutionAssumptions("HYPOTHETICAL_CODEX", "hypothetical_fixture", "syn:policy", "0", "1", "0.01",
                                               m.LotPolicy("syn:lot", 100, 100, 100, "whole_odd_remainder_only", 1000000), m.SettlementPolicy("syn:T+1", 1)),
            attempt=m.ExecutionAttempt("A", T, "2024-03-19", "open_auction"))
        parts.update(kw)
        return m.ExecutionRequest(**parts)

    def cx_continuous(self, quantity=200, capacity_qty=100, at=None, consumed=0):
        at = at or self.T10
        req = self.cx_request()
        return replace(req, order=replace(req.order, quantity=quantity, execution_phase="continuous"),
                       attempt=replace(req.attempt, phase="continuous", executed_at=at),
                       price=replace(req.price, observed_at=at, available_at=at, field="last_trade"),
                       capacity=replace(req.capacity, quantity=capacity_qty, observed_at=at, available_at=at, basis="available_at_attempt", consumed_quantity=consumed))

    def cx_sell(self, quantity, settled, capacity_qty, rule="whole_odd_remainder_only", consumed=0):
        req = self.cx_request()
        lot = m.LotPolicy("syn:lot", 100, 100, 100, rule, 1000000)
        return replace(req, decision=replace(req.decision, side="sell"), order=replace(req.order, side="sell", quantity=quantity),
                       account=replace(req.account, inventory=(m.InventoryLot(settled, "2024-03-18"),)),
                       capacity=replace(req.capacity, quantity=capacity_qty, consumed_quantity=consumed),
                       assumptions=replace(req.assumptions, lot_policy=lot))

    def test_hand_buy_reference(self):
        r = run("codex.hand_buy", self.cx_request())
        self.assertEqual(r.status, "filled")
        self.assertEqual(r.record["fill"]["fees"], {"commission": "5.00", "transfer_fee": "0.01", "stamp_duty": "0.00", "total": "5.01"})   # 1000 x 0.0003 = 0.30 < 5.00; 1000 x 0.00001 = 0.01
        self.assertEqual(r.record["ledger_entry"]["cash_delta"], "-1005.01")

    def test_p1_1_continuous_orders_live_until_the_actual_expiry_instant(self):
        partial = run("codex.p1_1.partial_continuous_10am", self.cx_continuous())
        self.assertEqual(partial.status, "partially_filled")
        self.assertEqual(partial.filled_quantity, 100)
        self.assertTrue(partial.record["order_live_after_attempt"])            # expires 15:00, attempt 10:00
        unfilled = run("codex.p1_1.unfilled_continuous_10am", self.cx_continuous(capacity_qty=0))
        self.assertUnfilled(unfilled, "capacity_exhausted")
        self.assertTrue(unfilled.record["order_live_after_attempt"])
        # later eligible retry of the remainder against the same capacity evidence (100 already consumed)
        retry = run("codex.p1_1.retry_11am_remainder", self.cx_continuous(quantity=100, capacity_qty=200, at=self.T11, consumed=100))
        self.assertEqual(retry.status, "filled")
        self.assertEqual(retry.record["fill"]["capacity"]["consumed_after"], 200)
        # boundary: a continuous attempt exactly at the close is a phase mismatch, one second later is outside the session,
        # the next session is expired
        at_close = run("codex.p1_1.continuous_at_close", self.cx_continuous(at="2024-03-19T15:00:00+08:00"))
        self.assertRejected(at_close, "execution_phase_mismatch")
        after_close = run("codex.p1_1.continuous_after_close", self.cx_continuous(at="2024-03-19T15:00:01+08:00"))
        self.assertRejected(after_close, "execution_outside_session")
        nxt = self.cx_continuous(at="2024-03-20T10:00:00+08:00")
        nxt = replace(nxt, attempt=replace(nxt.attempt, session="2024-03-20"),
                      tradability=replace(nxt.tradability, session="2024-03-20", observed_at="2024-03-20T09:15:00+08:00", available_at="2024-03-20T09:15:00+08:00"))
        self.assertRejected(run("codex.p1_1.continuous_next_session", nxt), "order_expired")
        # one second before the close the remainder is still live; a close-auction order on its expiry session is not
        late = run("codex.p1_1.continuous_14_59_59", self.cx_continuous(at="2024-03-19T14:59:59+08:00"))
        self.assertTrue(late.record["order_live_after_attempt"])
        base = self.cx_request()
        close_order = replace(base, order=replace(base.order, quantity=200, execution_phase="close_auction"),
                              attempt=replace(base.attempt, phase="close_auction", executed_at="2024-03-19T15:00:00+08:00"),
                              price=replace(base.price, observed_at="2024-03-19T15:00:00+08:00", available_at="2024-03-19T15:00:00+08:00", field="close_auction_print"),
                              capacity=replace(base.capacity, quantity=100, observed_at="2024-03-19T15:00:00+08:00", available_at="2024-03-19T15:00:00+08:00"))
        r = run("codex.p1_1.close_auction_partial_on_expiry_session", close_order)
        self.assertEqual(r.status, "partially_filled")
        self.assertFalse(r.record["order_live_after_attempt"])                 # documented final executable opportunity
        # open-auction convention: unfilled on the expiry session -> not live; on an earlier session of a 2-session order -> live
        oa = run("codex.p1_1.open_auction_unfilled_expiry_session", self.cx_request(capacity=None))
        self.assertFalse(oa.record["order_live_after_attempt"])
        two = self.cx_request(capacity=None)
        two = replace(two, order=replace(two.order, expiry_sessions=2))
        self.assertTrue(run("codex.p1_1.open_auction_unfilled_first_of_two", two).record["order_live_after_attempt"])

    def test_p1_2_odd_lot_semantics_within_raw_capacity(self):
        r50 = run("codex.p1_2.whole_odd_50_exact_capacity", self.cx_sell(50, 50, 50))
        self.assertEqual(r50.status, "filled")
        self.assertEqual(r50.filled_quantity, 50)
        r199 = run("codex.p1_2.whole_odd_199_exact_capacity", self.cx_sell(199, 199, 199))
        self.assertEqual(r199.status, "filled")
        self.assertEqual(r199.filled_quantity, 199)
        self.assertEqual(r199.record["fill"]["gross_amount"], "1990.00")     # 199 x 10.00 (zero slippage)
        # genuinely insufficient capacity: 49 shares cannot carry the whole 50-share odd remainder
        short = run("codex.p1_2.whole_odd_50_capacity_49", self.cx_sell(50, 50, 49))
        self.assertUnfilled(short, "capacity_below_minimum_lot")
        # 199 requested, capacity 150: one whole lot fills, the 99-share remainder must stay whole
        part = run("codex.p1_2.whole_odd_199_capacity_150", self.cx_sell(199, 199, 150))
        self.assertEqual(part.status, "partially_filled")
        self.assertEqual(part.filled_quantity, 100)
        self.assertEqual(part.record["fill"]["remaining_quantity"], 99)
        # 199 requested, capacity 99: the whole odd remainder fits, no whole lot does
        odd_first = run("codex.p1_2.whole_odd_199_capacity_99", self.cx_sell(199, 199, 99))
        self.assertEqual(odd_first.filled_quantity, 99)
        # under 'any' the partial fill is the raw remaining capacity
        any_part = run("codex.p1_2.any_199_capacity_150", self.cx_sell(199, 199, 150, rule="any"))
        self.assertEqual(any_part.filled_quantity, 150)
        any_full = run("codex.p1_2.any_50_capacity_50", self.cx_sell(50, 50, 50, rule="any"))
        self.assertEqual(any_full.filled_quantity, 50)
        # cumulative consumption of one capacity evidence
        first = run("codex.p1_2.cumulative_first_100", self.cx_sell(199, 199, 199, consumed=0))
        self.assertEqual(first.filled_quantity, 199)
        second = run("codex.p1_2.cumulative_after_100", self.cx_sell(199, 199, 199, consumed=100))
        self.assertEqual(second.filled_quantity, 99)                          # remaining 99 = whole odd remainder
        third = run("codex.p1_2.cumulative_exhausted", self.cx_sell(199, 199, 199, consumed=199))
        self.assertUnfilled(third, "capacity_exhausted")
        # buys keep whole-lot partial fills: 250 shares of allowance fill 200 of a 300 order
        buy = self.cx_request()
        buy = replace(buy, order=replace(buy.order, quantity=300), capacity=replace(buy.capacity, quantity=250))
        self.assertEqual(run("codex.p1_2.buy_partial_whole_lots", buy).filled_quantity, 200)

    def test_p1_3_calendar_published_after_the_decision_is_rejected(self):
        r = run("codex.p1_3.future_calendar", self.cx_request(calendar=self.cx_calendar(available_at="2025-01-01T00:00:00+08:00")))
        self.assertRejected(r, "calendar_not_available")
        self.assertIn("earliest required instant is the decision instant", r.reasons[0]["detail"])
        one_second_late = run("codex.p1_3.calendar_one_second_after_decision", self.cx_request(calendar=self.cx_calendar(available_at="2024-03-18T16:00:01+08:00")))
        self.assertRejected(one_second_late, "calendar_not_available")
        exact = run("codex.p1_3.calendar_available_at_decision", self.cx_request(calendar=self.cx_calendar(available_at="2024-03-18T16:00:00+08:00")))
        self.assertEqual(exact.status, "filled")

    def test_p1_4_consumed_settlement_session_is_bound_in_the_identity(self):
        reference = run("codex.p1_4.reference", self.cx_request())
        self.assertEqual(reference.record["ledger_entry"]["sellable_from_session"], "2024-03-20")
        self.assertEqual(reference.record["identities"]["calendar_prefix_last_session"], "2024-03-20")
        moved = run("codex.p1_4.future_settlement_suffix", self.cx_request(calendar=self.cx_calendar(("2024-03-18", "2024-03-19", "2024-03-22", "2024-03-25"))))
        self.assertEqual(moved.record["ledger_entry"]["sellable_from_session"], "2024-03-22")
        self.assertNotEqual(moved.record["identities"]["input_hash"], reference.record["identities"]["input_hash"])
        self.assertNotEqual(moved.result_hash, reference.result_hash)
        # sessions after the settlement session remain a free suffix
        extended = run("codex.p1_4.suffix_after_settlement", self.cx_request(calendar=self.cx_calendar(self.CX_SESSIONS + ("2024-03-22", "2024-03-25"))))
        self.assertEqual(extended.result_hash, reference.result_hash)
        self.assertEqual(extended.record["identities"]["input_hash"], reference.record["identities"]["input_hash"])

    def test_p1_5_result_is_independent_of_the_callers_decimal_context(self):
        import decimal
        reference = run("codex.p1_5.reference", self.cx_request())
        before = decimal.getcontext().copy()
        for name, prec, rounding in (("prec6_down", 6, decimal.ROUND_DOWN), ("prec1_up", 1, decimal.ROUND_UP), ("prec2_half_up", 2, decimal.ROUND_HALF_UP)):
            with decimal.localcontext() as ctx:
                ctx.prec = prec
                ctx.rounding = rounding
                ctx.traps[decimal.InvalidOperation] = False
                ctx.traps[decimal.Inexact] = True
                r = run(f"codex.p1_5.ambient_{name}", self.cx_request())
                self.assertEqual(r.record, reference.record, name)
                sell = run(f"codex.p1_5.ambient_{name}_sell_fees", self.cx_sell(199, 199, 199))
                self.assertEqual(sell.record["fill"]["fees"], {"commission": "5.00", "transfer_fee": "0.02", "stamp_duty": "1.00", "total": "6.02"})   # 1990 x 0.00001 = 0.0199 -> 0.02; x 0.0005 = 0.995 -> 1.00
                self.assertEqual(ctx.prec, prec)
        after = decimal.getcontext()
        self.assertEqual((after.prec, after.rounding, after.traps), (before.prec, before.rounding, before.traps))
        # numeric bounds are explicit: <= 12 decimal places and <= 24 significant digits pass; more is rejected; magnitude 1e16 is rejected
        long_ok = run("codex.p1_5.long_representation_12_places", self.cx_request(price=replace(self.cx_request().price, price="10.000000000000")))   # 12 places, tick aligned
        self.assertEqual(long_ok.status, "filled")
        self.assertEqual(long_ok.record, reference.record)
        long_bad = run("codex.p1_5.long_representation_13_places", self.cx_request(price=replace(self.cx_request().price, price="10.0000000000001")))
        self.assertRejected(long_bad, "invalid_input")
        self.assertIn("numeric bounds", long_bad.reasons[0]["detail"])
        digits_bad = run("codex.p1_5.long_representation_25_digits", self.cx_request(order=replace(self.cx_request().order, limit_price="1234567890123.000000000000")))
        self.assertRejected(digits_bad, "invalid_input")
        self.assertIn("numeric bounds", digits_bad.reasons[0]["detail"])
        huge = run("codex.p1_5.magnitude_1e16", self.cx_request(account=replace(self.cx_request().account, available_cash="10000000000000000.00")))
        self.assertRejected(huge, "invalid_input")
        rich = self.cx_request()
        rich = replace(rich, account=replace(rich.account, available_cash="999999999999999.99"), order=replace(rich.order, quantity=1_000_000), capacity=replace(rich.capacity, quantity=10**9))
        top = run("codex.p1_5.upper_boundary_buy", rich)
        self.assertEqual(top.status, "filled")
        self.assertEqual(top.record["fill"]["gross_amount"], "10000000.00")
        self.assertEqual(top.record["fill"]["fees"], {"commission": "3000.00", "transfer_fee": "100.00", "stamp_duty": "0.00", "total": "3100.00"})
        self.assertEqual(top.record["ledger_entry"]["cash_after"], "999999989996899.99")   # 999999999999999.99 - 10003100.00

    def test_p2_6_every_accepted_numeric_spelling_binds_one_identity(self):
        reference = run("codex.p2_6.reference", self.cx_request())
        base = self.cx_request()
        as_int = run("codex.p2_6.integer_price", replace(base, price=replace(base.price, price=10)))
        self.assertEqual(as_int.record, reference.record)
        as_dec = run("codex.p2_6.decimal_price_10_0", replace(base, price=replace(base.price, price=Decimal("10.0"))))
        self.assertEqual(as_dec.record, reference.record)
        mixed = replace(base, order=replace(base.order, limit_price=10), account=replace(base.account, available_cash=10000),
                        tradability=replace(base.tradability, limit_up_price=Decimal("11"), limit_down_price="9"),
                        fee_schedule=replace(base.fee_schedule, min_commission=5), assumptions=replace(base.assumptions, tick_size=Decimal("0.010"), slippage_rate=0))
        self.assertEqual(run("codex.p2_6.mixed_spellings", mixed).record, reference.record)
        # true quantities stay typed integers in the identity record; identifiers are literal
        rec = m._record(base.order)
        self.assertIs(type(rec["quantity"]), int)
        self.assertEqual(rec["limit_price"], "10")
        self.assertEqual(m._record(base.capacity)["quantity"], 1000)
        self.assertEqual(m._record(replace(base.capacity, quantity="1000.50", unit="CNY"))["quantity"], "1000.5")
        self.assertEqual(m._record(base.order)["order_id"], "O")


if __name__ == "__main__":
    argv = [a for a in sys.argv if not a.startswith("--dump=")]
    dump = next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--dump=")), None)
    program = unittest.main(argv=argv, exit=False, verbosity=2)
    if dump:
        Path(dump).write_text(json.dumps(RESULT_LOG, indent=1, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    sys.exit(0 if program.result.wasSuccessful() else 1)
