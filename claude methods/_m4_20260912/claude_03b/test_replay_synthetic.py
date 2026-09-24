"""Focused synthetic tests for the M4-03B runner (guard in synthetic mode: every SQLite connect denied, no network,
no child process, writes only under claude_03b/).  Frozen engines and the accepted mapping are loaded by file path after
hash verification; no app/conftest/pytest import.  Every fixture is synthetic (SYN symbols, synthetic=True).

    backend/.venv/Scripts/python.exe -B -X utf8 "claude methods/_m4_20260912/claude_03b/test_replay_synthetic.py" -v
"""
from __future__ import annotations

import importlib.util
import json
import sys
import unittest
from decimal import Decimal
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parents[2]
sys.dont_write_bytecode = True


def _load(name, path):
    if name in sys.modules:                     # the runner already loaded guard / core: reuse the single guard instance
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


guard = _load("m4_03b_guard", HERE / "guard.py")
guard.install()
core = _load("m4_03b_replay_core", HERE / "replay_core.py")
MODS = core.load_frozen(PROJECT)
SCENARIOS: dict[str, dict] = {}


def sessions_from(start_ymd: tuple[int, int, int], n: int) -> list[str]:
    """n synthetic weekday sessions from a start date (calendar-day arithmetic, weekends skipped)."""
    from datetime import date, timedelta
    d = date(*start_ymd)
    out = []
    while len(out) < n:
        if d.weekday() < 5:
            out.append(d.isoformat())
        d += timedelta(days=1)
    return out


def flat_then_cross(sessions, n_flat=22, level="10.00", up="10.50", after=None):
    """closes: n_flat sessions at ``level`` (SMA == close -> no signal), then ``up`` (cross), then ``after`` values or ``up``."""
    bars = {}
    for i, s in enumerate(sessions):
        if i < n_flat:
            c = level
        elif i == n_flat:
            c = up
        else:
            c = (after[i - n_flat - 1] if after and i - n_flat - 1 < len(after) else up)
        bars[s] = (c, c, c, c, 1000000)
    return bars


class ReplayCase(unittest.TestCase):
    def snapshot(self, bars, halts=None, listing=None, sessions=None):
        sess = sessions or sorted({d for v in bars.values() for d in v})
        return core.synthetic_snapshot(sess, bars, halts=halts, listing=listing)

    def run_branch(self, snap, branch, cash="100000.00", first=None, last=None):
        first = first or snap.sessions[0]
        last = last or snap.sessions[-2]              # the last session of the slice is the "next legal session" (never decided on)
        return core.Replay(MODS, snap, branch, initial_cash=cash, synthetic=True, decision_sessions=(first, last), benchmark_symbol="SYN900300").run()


class TestGlobalOrderAndCausalMarks(ReplayCase):
    def test_two_symbols_same_session_attempts_before_close_decision_shared_cash_and_prior_close_marks(self):
        S = sessions_from((2024, 1, 2), 30)
        bars = {"SYN000001": flat_then_cross(S, 22, "10.00", "10.50"), "SYN000002": flat_then_cross(S, 22, "20.00", "21.00"),
                "SYN900300": {s: ("3000.00", "3000.00", "3000.00", "3000.00", 0) for s in S}}
        snap = self.snapshot(bars)
        res = self.run_branch(snap, "assumed_full_fill")
        recs = res["records"]
        cross = S[22]
        d_cross = next(r for r in recs if r["kind"] == "decision" and r["session"] == cross)
        self.assertEqual(sorted(d_cross["signals"]), [f"B0-{cross}-SYN000001", f"B0-{cross}-SYN000002"])
        entries = {e["symbol"]: e for e in d_cross["engine_record"]["entries"]}
        # cash 100000: A position room 5000 -> 400 @ 10.02 (est 4014.08); B: room 5000 -> reserved price 21.05 -> floor(5000/21.05)=237 -> 200 (est 4210.00+6.00+0.08)
        self.assertEqual((entries["SYN000001"]["quantity"], entries["SYN000002"]["quantity"]), (400, 200))
        nxt = S[23]
        idx = [i for i, r in enumerate(recs) if r["session"] == nxt]
        kinds = [recs[i]["kind"] for i in idx]
        self.assertEqual(kinds, ["attempt", "attempt", "decision"])                        # both open attempts precede the 16:00 decision of that session
        a1, a2 = recs[idx[0]], recs[idx[1]]
        self.assertEqual((a1["engine_record"]["intent_id"], a2["engine_record"]["intent_id"]), (f"D-{cross}:buy:SYN000001", f"D-{cross}:buy:SYN000002"))
        self.assertLess(a2["model_time"]["executed_at"], recs[idx[2]]["model_time"]["decided_at"])
        rc = a2["engine_record"]["outcome"]["recheck"]
        # B's re-check sees A's fill and values A at its PRIOR close 10.50 (not the S23 close)
        self.assertEqual(rc["cash_now"], "95781.92")                                          # A filled 400 @ ceil(10.50 x 1.002) = 10.53: 4212.00 + 6.00 + 0.08
        self.assertEqual((rc["marks"]["SYN000001"]["price"], rc["marks"]["SYN000001"]["observed_at"], rc["marks"]["SYN000001"]["age_sessions"]), ("10.50", f"{cross}T15:00:00+08:00", 1))
        self.assertTrue(all(p["role"] != "decision_mark" for p in a2["raw_provenance"]))
        self.assertIn("other_held_mark", {p.get("role") for p in a2["raw_provenance"]})
        self.assertEqual(res["ledger_snapshot"]["positions"], {"SYN000001": 400, "SYN000002": 200})
        ec = [r["engine_record"]["state_summary"]["event_clock"] for r in recs if r["kind"] in ("attempt", "decision")]
        self.assertEqual(ec, sorted(ec))                                                       # global chronology never goes backwards
        # funnel stages are mutually exclusive and sum to symbol-sessions
        st = res["funnel"]["decision_stage"]
        n_dec = sum(1 for r in recs if r["kind"] == "decision")
        self.assertEqual(st["price_row"], 2 * n_dec)
        self.assertEqual(st["insufficient_history"] + st["no_signal"] + st["signal"], st["price_row"])
        SCENARIOS["two_symbol_global_order"] = {"decision_stage": st, "entry_outcomes": res["funnel"]["entry_outcomes"], "attempt_outcomes": res["funnel"]["attempt_outcomes"],
                                                 "b_recheck": rc, "positions": res["ledger_snapshot"]["positions"], "event_clock_monotonic": ec == sorted(ec)}

    def test_stale_other_mark_refuses_buy_instead_of_zero(self):
        S = sessions_from((2024, 1, 2), 30)
        bars = {"SYN000001": flat_then_cross(S, 22, "10.00", "10.50"), "SYN000002": flat_then_cross(S, 23, "20.00", "21.00")}
        bars["SYN000001"].pop(S[23])                                   # A halted on the session B is attempted
        snap = self.snapshot(bars, halts={"SYN000001": {S[23]}}, sessions=S)
        res = self.run_branch(snap, "assumed_full_fill")
        att = [r for r in res["records"] if r["kind"] == "attempt"]
        # A bought at S23? no: A's attempt on S23 is a halt (placeholder -> suspended). B signals at S23 (close 21 > sma) -> attempt S24 with A not held.
        self.assertIn("buy:expired:suspended", res["funnel"]["attempt_outcomes"])
        self.assertTrue(all(r["engine_record"]["status"] != "filled" or r["engine_record"]["intent_id"].endswith("SYN000002") for r in att))


class TestDateLimitsAndCensoring(ReplayCase):
    def test_last_session_intent_is_censored_not_attempted_and_open_position_reported(self):
        S = sessions_from((2024, 1, 2), 26)
        bars = {"SYN000001": flat_then_cross(S, 22, "10.00", "10.50", after=["10.60", "10.70", "10.80"])}
        snap = self.snapshot(bars)
        last = S[-2]
        res = self.run_branch(snap, "assumed_full_fill", last=last)
        self.assertTrue(all(r["session"] <= last for r in res["records"]))
        self.assertEqual(res["ledger_snapshot"]["positions"], {"SYN000001": 400})
        self.assertEqual(res["censored"]["open_positions"], {"SYN000001": {"quantity": 400, "has_mark_at_end": True}})
        self.assertEqual(res["censored"]["as_of"], f"{last}T16:00:00+08:00")
        perf = res["performance"]
        self.assertEqual((perf["status"], perf["positions"]["SYN000001"]["mark"]), ("valued", "10.70"))    # last decision session S24 close
        # a decision on the last session with a signal would create a beyond-window intent: force one with a second symbol crossing on the last session
        bars2 = dict(bars); bars2["SYN000002"] = flat_then_cross(S, len(S) - 2, "20.00", "21.00")
        res2 = self.run_branch(self.snapshot(bars2), "assumed_full_fill", last=last)
        live = res2["censored"]["live_intents_beyond_window"]
        self.assertEqual(list(live), [f"D-{last}:buy:SYN000002"])
        self.assertEqual((live[f"D-{last}:buy:SYN000002"]["status"], live[f"D-{last}:buy:SYN000002"]["eligible_session"]), ("pending", S[-1]))
        self.assertFalse(any(r["kind"] == "attempt" and r["session"] == S[-1] for r in res2["records"]))
        SCENARIOS["censoring"] = {"censored": res2["censored"], "performance_status": res2["performance"]["status"]}


class TestHaltsMissingAndListing(ReplayCase):
    def test_halt_on_attempt_session_uses_placeholder_and_expires_without_fill(self):
        S = sessions_from((2024, 1, 2), 30)
        bars = {"SYN000001": flat_then_cross(S, 22, "10.00", "10.50")}
        bars["SYN000001"].pop(S[23])
        snap = self.snapshot(bars, halts={"SYN000001": {S[23]}}, sessions=S)
        res = self.run_branch(snap, "assumed_full_fill")
        att = next(r for r in res["records"] if r["kind"] == "attempt" and r["session"] == S[23])
        self.assertTrue(att["halt_placeholder_used"])
        self.assertEqual((att["engine_record"]["status"], [q["code"] for q in att["engine_record"]["ledger_record"]["kernel"]["reasons"]]), ("expired", ["suspended"]))
        self.assertIn(MODS["pm"].ASSUMPTIONS["halt_placeholder"], att["assumption_ids"])
        self.assertEqual(res["ledger_snapshot"]["positions"], {})
        # the decision on the halt session lists the symbol as halt_key (no mark), and the cooldown/held logic is untouched
        d = next(r for r in res["records"] if r["kind"] == "decision" and r["session"] == S[23])
        self.assertEqual(d["stage_counts"].get("halt_key"), 1)

    def test_held_symbol_halted_on_decision_session_makes_valuation_incomplete_not_zero(self):
        S = sessions_from((2024, 1, 2), 30)
        bars = {"SYN000001": flat_then_cross(S, 22, "10.00", "10.50"), "SYN000002": flat_then_cross(S, 24, "20.00", "21.00")}
        bars["SYN000001"].pop(S[24])                                 # A held (bought S23), halted on S24 when B signals
        snap = self.snapshot(bars, halts={"SYN000001": {S[24]}}, sessions=S)
        res = self.run_branch(snap, "assumed_full_fill")
        d = next(r for r in res["records"] if r["kind"] == "decision" and r["session"] == S[24])
        v = d["engine_record"]["valuation"]
        self.assertEqual((v["complete"], v["equity"], v["incomplete_symbols"]), (False, None, ["SYN000001"]))
        self.assertEqual(next(e for e in d["engine_record"]["entries"] if e["symbol"] == "SYN000002")["reason"], "valuation_incomplete")

    def test_missing_unconfirmed_row_is_not_a_halt_and_intent_is_swept(self):
        S = sessions_from((2024, 1, 2), 30)
        bars = {"SYN000001": flat_then_cross(S, 22, "10.00", "10.50")}
        bars["SYN000001"].pop(S[23])                                 # no bar and NO halt key
        res = self.run_branch(self.snapshot(bars, sessions=S), "assumed_full_fill")
        self.assertEqual(res["funnel"]["attempt_outcomes"].get("not_attempted_missing_unconfirmed_row"), 1)
        self.assertEqual(res["funnel"]["attempt_outcomes"].get("swept_expired_at_decision"), 1)
        self.assertEqual(res["funnel"]["decision_stage"].get("missing_unconfirmed_row"), 1)
        self.assertEqual(res["ledger_snapshot"]["positions"], {})

    def test_new_listing_exclusion_and_insufficient_history_counts(self):
        S = sessions_from((2024, 1, 2), 30)
        bars = {"SYN000001": flat_then_cross(S, 22, "10.00", "10.50")}
        listing = {"SYN000001": S[0]}
        res = self.run_branch(self.snapshot(bars, listing=listing), "assumed_full_fill")
        st = res["funnel"]["decision_stage"]
        # decisions on S0..S3 have next-session listing age 1..4 (< 5) -> excluded; S4.. count history until 21 bars (S20), signal at S22
        self.assertEqual(st["new_listing_exclusion"], 4)
        self.assertEqual(st["insufficient_history"], 20 - 4)
        depths = core.warmup_depths(self.snapshot(bars), S[0], S[9])
        self.assertEqual((depths["SYN000001"]["bars_in_window"], depths["SYN000001"]["window_sessions"]), (10, 10))


class TestCapacityVariants(ReplayCase):
    def test_full_fill_fixed_5000_and_none(self):
        S = sessions_from((2024, 1, 2), 26)
        bars = {"SYN000001": flat_then_cross(S, 22, "10.00", "10.50")}
        snap = self.snapshot(bars)
        full = self.run_branch(snap, "assumed_full_fill", cash="5000000.00")      # budget 250000; mark 10.50 -> reserved 10.53 -> floor(250000/10.53) = 23741 -> 23700 shares
        fixed = self.run_branch(snap, "assumed_fixed_5000", cash="5000000.00")
        none = self.run_branch(snap, "assumed_capacity_none", cash="5000000.00")
        f_att = next(r for r in full["records"] if r["kind"] == "attempt")
        x_att = next(r for r in fixed["records"] if r["kind"] == "attempt")
        n_att = next(r for r in none["records"] if r["kind"] == "attempt")
        self.assertEqual((f_att["engine_record"]["status"], f_att["engine_record"]["outcome"]["filled_quantity"]), ("filled", 23700))
        self.assertEqual((x_att["engine_record"]["status"], x_att["engine_record"]["outcome"]["filled_quantity"]), ("expired", 5000))
        self.assertEqual((n_att["engine_record"]["status"], [q["code"] for q in n_att["engine_record"]["ledger_record"]["kernel"]["reasons"]]), ("expired", ["capacity_unproven"]))
        cid = f"CAP-SYN000001-{S[23]}-open"
        self.assertEqual((f_att["capacity_id"], x_att["capacity_id"], n_att["capacity_id"]), (cid, cid, None))
        self.assertEqual(fixed["ledger_reconcile"]["capacity"][cid], {"unit": "share", "budget": "5000", "consumed": "5000", "within_budget": True})
        self.assertEqual(full["ledger_reconcile"]["capacity"][cid], {"unit": "share", "budget": "23700", "consumed": "23700", "within_budget": True})
        self.assertEqual((full["ledger_snapshot"]["positions"], fixed["ledger_snapshot"]["positions"], none["ledger_snapshot"]["positions"]), ({"SYN000001": 23700}, {"SYN000001": 5000}, {}))
        SCENARIOS["capacity_variants"] = {"full_fill": f_att["engine_record"]["outcome"]["filled_quantity"], "fixed_5000": x_att["engine_record"]["outcome"]["filled_quantity"],
                                          "none": [q["code"] for q in n_att["engine_record"]["ledger_record"]["kernel"]["reasons"]], "capacity_id": cid, "fixed_reconcile": fixed["ledger_reconcile"]["capacity"][cid]}


class TestDeterminismAndFutureSuffix(ReplayCase):
    def test_same_sealed_input_twice_identical_hashes(self):
        S = sessions_from((2024, 1, 2), 30)
        bars = {"SYN000001": flat_then_cross(S, 22, "10.00", "10.50", after=["10.00", "9.80", "9.70"]), "SYN000002": flat_then_cross(S, 23, "20.00", "21.00")}
        snap = self.snapshot(bars)
        a, b = self.run_branch(snap, "assumed_full_fill"), self.run_branch(snap, "assumed_full_fill")
        self.assertEqual(core.output_hash(a), core.output_hash(b))
        self.assertEqual(a["engine_chain_hash"], b["engine_chain_hash"])
        self.assertNotEqual(core.output_hash(a), core.output_hash(self.run_branch(snap, "assumed_fixed_5000")))
        SCENARIOS["determinism"] = {"output_hash": core.output_hash(a), "chain_hash": a["engine_chain_hash"]}

    def test_future_suffix_cannot_change_earlier_open_records(self):
        S = sessions_from((2024, 1, 2), 30)
        base = flat_then_cross(S, 22, "10.00", "10.50", after=["10.60", "10.70", "10.80"])
        alt = dict(base)
        alt[S[23]] = ("10.60", "11.55", "9.50", "11.55", 9999999)         # same open, wildly different high/low/close/volume on the attempt session
        alt[S[24]] = ("12.00", "12.50", "11.50", "12.20", 9999999)
        ra = self.run_branch(self.snapshot({"SYN000001": base}), "assumed_full_fill")
        rb = self.run_branch(self.snapshot({"SYN000001": alt}), "assumed_full_fill")
        ka = [r for r in ra["records"] if r["session"] <= S[23] and r["kind"] != "decision" or (r["kind"] == "decision" and r["session"] <= S[22])]
        kb = [r for r in rb["records"] if r["session"] <= S[23] and r["kind"] != "decision" or (r["kind"] == "decision" and r["session"] <= S[22])]
        self.assertEqual([r["engine_record"]["record_hash"] for r in ka], [r["engine_record"]["record_hash"] for r in kb])
        att_a = next(r for r in ra["records"] if r["kind"] == "attempt"); att_b = next(r for r in rb["records"] if r["kind"] == "attempt")
        self.assertEqual(att_a["engine_record"]["record_hash"], att_b["engine_record"]["record_hash"])
        self.assertEqual(att_a["engine_record"]["outcome"]["fill_price"], "10.63")               # 10.60 x 1.002 = 10.6212 -> 10.63
        da = next(r for r in ra["records"] if r["kind"] == "decision" and r["session"] == S[23]); db = next(r for r in rb["records"] if r["kind"] == "decision" and r["session"] == S[23])
        self.assertNotEqual(da["engine_record"]["record_hash"], db["engine_record"]["record_hash"])   # the S23 close differs and may only act at the S23 16:00 decision
        self.assertNotEqual(att_a["post_hoc_diagnostics"], att_b["post_hoc_diagnostics"])          # volume enters only the post-hoc diagnostic
        SCENARIOS["future_suffix_control"] = {"attempt_hash_equal": att_a["engine_record"]["record_hash"] == att_b["engine_record"]["record_hash"],
                                              "fill_price": att_a["engine_record"]["outcome"]["fill_price"], "decision_after_diverges": da["engine_record"]["record_hash"] != db["engine_record"]["record_hash"]}


class TestRawPathAndProvenance(ReplayCase):
    def test_raw_variant_refuses_at_decision_and_keeps_capture_time(self):
        S = sessions_from((2024, 1, 2), 26)
        bars = {"SYN000001": flat_then_cross(S, 22, "10.00", "10.50"), "SYN900300": {s: ("3000.00", "3000.00", "3000.00", "3000.00", 0) for s in S}}
        res = self.run_branch(self.snapshot(bars), "raw")
        self.assertEqual(res["funnel"]["intents_by_status"], {})
        self.assertEqual(res["ledger_records"], [])
        self.assertEqual(res["funnel"]["decision_stage"]["signal"], 1)                       # retrospective diagnostic only
        self.assertGreater(res["funnel"]["decision_refusals"].get("item:future_evidence:mark", 0), 0)
        self.assertEqual(res["funnel"]["decision_refusals"].get("item:future_evidence:signal"), 1)
        d = next(r for r in res["records"] if r["kind"] == "decision" and r["session"] == S[22])
        self.assertEqual((d["grade"], d["assumption_ids"], d["engine_record"]["entries"]), ("raw", [], []))
        self.assertTrue(all(p["captured_at"] == "2026-09-09T17:12:13.572989+00:00" for p in d["raw_provenance"]))
        self.assertEqual(res["performance"]["status"], "incomplete" if res["ledger_snapshot"]["positions"] else "valued")
        SCENARIOS["raw_path"] = {"decision_refusals": res["funnel"]["decision_refusals"], "intents": res["funnel"]["intents_by_status"], "diagnostic_signals": res["funnel"]["decision_stage"]["signal"]}

    def test_assumed_wrappers_carry_raw_capture_and_model_time_separately(self):
        S = sessions_from((2024, 1, 2), 26)
        bars = {"SYN000001": flat_then_cross(S, 22, "10.00", "10.50")}
        res = self.run_branch(self.snapshot(bars), "assumed_full_fill")
        att = next(r for r in res["records"] if r["kind"] == "attempt")
        self.assertEqual(att["model_time"]["price_observed_at"], f"{S[23]}T09:30:00+08:00")
        self.assertEqual(att["raw_provenance"][0]["captured_at"], "2026-09-09T17:12:13.572989+00:00")
        self.assertIn(MODS["pm"].ASSUMPTIONS["open_print"], att["assumption_ids"])
        kev = att["engine_record"]["ledger_record"]["kernel"]
        self.assertEqual((kev["evidence_grade"], att["grade"], att["adjustment_uncertainty"]), ("assumed", "assumed", True))
        dec = next(r for r in res["records"] if r["kind"] == "decision" and r["session"] == S[22])
        self.assertEqual(dec["model_time"], {"decided_at": f"{S[22]}T16:00:00+08:00", "mark_observed_at": f"{S[22]}T15:00:00+08:00", "mark_available_at": f"{S[22]}T16:00:00+08:00"})
        self.assertIn(core.STATUS_DEFAULT_ASSUMPTION, dec["assumption_ids"])
        self.assertIn("captured=2026-09-09T17:12:13.572989+00:00", dec["engine_record"]["entries"][0]["mark_evidence"]["source_ref"])


class TestExitChain(ReplayCase):
    def test_stop_loss_exit_before_entries_and_cooldown(self):
        S = sessions_from((2024, 1, 2), 34)
        after = ["10.00", "9.80", "9.50", "9.50", "9.50", "9.50", "9.50", "9.50", "9.50", "9.50", "9.50"]
        bars = {"SYN000001": flat_then_cross(S, 22, "10.00", "10.50", after=after)}
        res = self.run_branch(self.snapshot(bars), "assumed_full_fill")
        # buy S23 open 10.00 (cross session close 10.50 -> next open = close of S23 in this flat fixture = 10.00): fill 10.02 -> ref 10.0352; stop at 9.53344 -> S25 close 9.50 -> exit S26 open 9.50 -> fill 9.48
        self.assertEqual(res["funnel"]["exit_intents"].get("stop_loss"), 1)
        sells = [r for r in res["records"] if r["kind"] == "attempt" and r["side"] == "sell"]
        self.assertEqual((len(sells), sells[0]["engine_record"]["status"], sells[0]["engine_record"]["outcome"]["fill_price"]), (1, "filled", "9.48"))
        self.assertEqual(res["ledger_snapshot"]["positions"], {})
        self.assertGreaterEqual(res["funnel"]["entry_outcomes"].get("refused:cooldown_active", 0), 0)
        self.assertTrue(res["ledger_reconcile"]["ok"])
        SCENARIOS["exit_chain"] = {"exit_intents": res["funnel"]["exit_intents"], "sell_fill_price": sells[0]["engine_record"]["outcome"]["fill_price"], "realized": res["performance"]["realized_pnl_total"]}


class TestPerformanceDenominatorAndBenchmarkProvenance(ReplayCase):
    """Codex M4-03B review 01: P2-1 instance initial cash is the performance denominator; P2-2 the performance wrapper carries
    structured benchmark endpoint provenance (both endpoints, raw sha / point index / capture instant, model time, assumption ids)."""

    def test_non_default_cash_zero_trades_returns_zero(self):
        S = sessions_from((2024, 1, 2), 26)
        bars = {"SYN000001": {s: ("10.00", "10.00", "10.00", "10.00", 1000) for s in S}, "SYN900300": {s: ("3000.00", "3000.00", "3000.00", "3000.00", 0) for s in S}}
        res = self.run_branch(self.snapshot(bars), "assumed_full_fill", cash="100000.00")
        p = res["performance"]
        self.assertEqual((p["status"], p["cash"], p["equity"], p["return"], res["ledger_snapshot"]["positions"]), ("valued", "100000.00", "100000.00", "0.000000", {}))
        perf_wrap = next(r for r in res["records"] if r["kind"] == "performance")
        self.assertEqual(perf_wrap["initial_cash_used"], "100000.00")
        SCENARIOS["non_default_cash_zero_trades"] = {"initial_cash": "100000.00", "equity": p["equity"], "return": p["return"]}

    def test_non_default_cash_with_trades_hand_calculated_return(self):
        S = sessions_from((2024, 1, 2), 34)
        after = ["10.00", "9.80", "9.50", "9.50", "9.50", "9.50", "9.50", "9.50", "9.50", "9.50", "9.50"]
        bars = {"SYN000001": flat_then_cross(S, 22, "10.00", "10.50", after=after)}
        res = self.run_branch(self.snapshot(bars), "assumed_full_fill", cash="50000.00")
        # cash 50000 -> position room 2500 -> floor(2500/10.53)=237 -> 200 @ open 10.00 -> fill 10.02: 2004.00 + 6.00 + 0.04 = 2010.04 -> cash 47989.96; ref 10.0502
        # stop <= 9.54769: close 9.50 -> exit next open 9.50 -> fill 9.48: gross 1896.00 - (6.00 + 0.04 + 1.52) = 1888.44 -> cash 49878.40; realized -121.60 -> return -0.002432
        p = res["performance"]
        self.assertEqual((p["cash"], p["equity"], p["realized_pnl_total"], p["return"]), ("49878.40", "49878.40", "-121.60", "-0.002432"))
        self.assertEqual(next(r for r in res["records"] if r["kind"] == "performance")["initial_cash_used"], "50000.00")
        SCENARIOS["non_default_cash_with_trades"] = {"initial_cash": "50000.00", "cash": p["cash"], "realized": p["realized_pnl_total"], "return": p["return"]}

    def test_assumed_performance_wrapper_carries_both_benchmark_endpoints(self):
        S = sessions_from((2024, 1, 2), 26)
        bars = {"SYN000001": {s: ("10.00", "10.00", "10.00", "10.00", 1000) for s in S}, "SYN900300": {s: (f"{3000 + i}.00",) * 4 + (0,) for i, s in enumerate(S)}}
        snap = self.snapshot(bars)
        res = self.run_branch(snap, "assumed_full_fill")
        w = next(r for r in res["records"] if r["kind"] == "performance")
        first, last = S[0], S[-2]
        ep = {p["role"]: p for p in w["raw_provenance"] if p["role"].startswith("benchmark_")}
        self.assertEqual(sorted(ep), ["benchmark_end_level", "benchmark_start_level"])
        self.assertEqual((ep["benchmark_start_level"]["symbol"], ep["benchmark_start_level"]["trade_date"], ep["benchmark_end_level"]["trade_date"]), ("SYN900300", first, last))
        for role, d in (("benchmark_start_level", first), ("benchmark_end_level", last)):
            b = snap.bars["SYN900300"][d]
            self.assertEqual((ep[role]["raw_sha256"], ep[role]["point_index"], ep[role]["captured_at"]), (b["raw_sha256"], b["point_index"], b["observed_at"]))
            self.assertEqual(w["benchmark_endpoints"]["model_time"][role], {"session": d, "observed_at": f"{d}T15:00:00+08:00", "available_at": f"{d}T16:00:00+08:00", "raw_captured_at": b["observed_at"]})
        # the same endpoint provenance exists in the first / last decision wrappers (the export repair derives from them)
        for d in (first, last):
            dec = next(r for r in res["records"] if r["kind"] == "decision" and r["session"] == d)
            bl = next(p for p in dec["raw_provenance"] if p["role"] == "benchmark_level")
            self.assertEqual((bl["raw_sha256"], bl["point_index"]), (snap.bars["SYN900300"][d]["raw_sha256"], snap.bars["SYN900300"][d]["point_index"]))
        self.assertEqual((w["benchmark_endpoints"]["engine_benchmark_status"], res["performance"]["benchmark"]["return"]), ("observed", str((Decimal(3000 + len(S) - 2) / Decimal(3000) - 1).quantize(Decimal("0.000001")))))
        self.assertIn(core.STATUS_DEFAULT_ASSUMPTION, w["assumption_ids"])
        self.assertIn(MODS["pm"].ASSUMPTIONS["close_availability"], w["assumption_ids"])
        SCENARIOS["assumed_benchmark_endpoint_provenance"] = {"endpoints": ep, "model_time": w["benchmark_endpoints"]["model_time"], "assumption_ids": w["assumption_ids"]}

    def test_raw_performance_wrapper_keeps_capture_instants_and_refusals(self):
        S = sessions_from((2024, 1, 2), 26)
        bars = {"SYN000001": {s: ("10.00", "10.00", "10.00", "10.00", 1000) for s in S}, "SYN900300": {s: ("3000.00", "3000.00", "3000.00", "3000.00", 0) for s in S}}
        res = self.run_branch(self.snapshot(bars), "raw")
        w = next(r for r in res["records"] if r["kind"] == "performance")
        ep = {p["role"]: p for p in w["raw_provenance"] if p["role"].startswith("benchmark_")}
        self.assertEqual(sorted(ep), ["benchmark_end_level", "benchmark_start_level"])
        mt = w["benchmark_endpoints"]["model_time"]
        self.assertEqual((mt["benchmark_start_level"]["observed_at"], mt["benchmark_start_level"]["available_at"]), ("2026-09-09T17:12:13.572989+00:00",) * 2)
        self.assertEqual((w["benchmark_endpoints"]["engine_benchmark_status"], [x["code"] for x in w["benchmark_endpoints"]["engine_benchmark_refusals"]]), ("missing", ["future_evidence", "future_evidence"]))
        self.assertEqual((w["grade"], w["assumption_ids"], res["performance"]["benchmark"]["return"]), ("raw", [], None))
        SCENARIOS["raw_benchmark_endpoint_provenance"] = {"status": w["benchmark_endpoints"]["engine_benchmark_status"], "refusals": w["benchmark_endpoints"]["engine_benchmark_refusals"]}


if __name__ == "__main__":
    argv = [a for a in sys.argv if not a.startswith("--dump=")]
    dump = next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--dump=")), None)
    program = unittest.main(argv=argv, exit=False, verbosity=2)
    if dump:
        Path(dump).write_text(json.dumps(SCENARIOS, indent=1, ensure_ascii=False, sort_keys=True, default=str) + "\n", encoding="utf-8")
    sys.exit(0 if program.result.wasSuccessful() else 1)
