"""Guarded static validator for the M4-03A qualification matrix.

What it proves (and records in claude_03a/evidence/validation_receipt.json):
  1. every pinned input (task file, three M4 freezes, historical evidence sources, accepted modules, two candidate
     databases by hash/size/sidecar-absence) matches the hashes recorded in qualification.json - byte reads only;
  2. the matrix covers the twelve required execution requirements, every row carries exact evidence refs, a
     development-coverage statement, an availability class, a verdict from the fixed vocabulary, three mode
     consequences and a non-empty consequence; the missing/unknown handling is explicit (a `missing` row can never be
     strict-eligible and can only be `assumption_required` / `ineligible` under hypothetical replay);
  3. every source-line anchor still points at the quoted text in the pinned module;
  4. the numbers quoted in the matrix are recomputed from the pinned metadata (audit result, metadata index, M2
     qualification bundle, pilot manifest) - no price row is read;
  5. safety flags are unchanged;
  6. tiny synthetic cases through the FROZEN kernel (loaded by file path, hash-verified; no app/conftest import):
     absent execution evidence stays ineligible (capacity_unproven), a 2026 capture instant cannot become
     contemporaneous proof (evidence_available_after_execution / input_not_available_at_decision /
     calendar_not_available), a declared assumption keeps its label (evidence_grade='assumed', assumptions_used), and
     the matrix classifier never grants strict eligibility to a non-contemporaneous availability class;
  7. (delivery 02, Codex review 01) the causal mapping of proposal_mapping.py through the complete FROZEN
     risk -> ledger -> kernel -> exit chain on synthetic bars: assumed-variant smoke (entry, stop exit, cooldown,
     re-entry, performance) with hand-calculated numbers and assumption labels in every record; strict-raw refusals with
     their actual reasons (decision-stage future_evidence, attempt-stage future_evidence); capacity-removal sensitivity
     of the assumed chain (capacity_unproven, no fill, expired); future-suffix invariance (high/low/close/volume of the
     attempt session and later bars change nothing before they become available); limit_state from the open print only;
     capacity model consistency (100 / 400 full fill, cumulative exhaustion, fixed 5 000 partial fill); post-hoc ex-date flag.

Guards: audit hook + monkeypatches deny sqlite3.connect (also the in-memory probe), sockets, subprocess and any file
write outside claude_03a/; bytecode disabled; the guard self-check runs first and its denials are recorded.

    backend/.venv/Scripts/python.exe -B -X utf8 "claude methods/_m4_20260912/claude_03a/validate_qualification.py"
"""
from __future__ import annotations

import csv
import hashlib
import importlib.util
import json
import os
import socket
import sqlite3
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
PROJECT = HERE.parents[2]
M4 = HERE.parent
EVIDENCE = HERE / "evidence"
ALLOWED_WRITE_ROOT = HERE.resolve()
TASK_FILE = "claude methods/M4_03A_HISTORICAL_QUALIFICATION_CLAUDE_TASK_20260912.md"
TASK_SHA = "10c0cc348a1dd42b1406ab101c5abd199c7a84553020572e22012301bc9431c9"
FREEZES = {"execution_freeze.json": "8a74233f21740f365b1c286d5c735dd4ead42c2ad00016ac9823e6ee5814e3f3",
           "portfolio_freeze.json": "e6fc61de18184a7cbbb3756a02fc8697e7c59f14ef836085b7a1b0c46fa3d281",
           "risk_freeze.json": "371505a47187c680bad2439abf656a5fa62bd707c5a8383dcf8c614f85186e10"}
REQUIRED_ROWS = ["R01_unadjusted_ohlc_units", "R02_calendar_session_next_legal_point", "R03_listing_board_lot_tick", "R04_historical_st_and_price_bands",
                 "R05_suspension_timing", "R06_corporate_actions_adjustments", "R07_delisting_terminal_value", "R08_capacity_auction_vs_full_day_volume",
                 "R09_fees_effective_dates", "R10_marks_and_benchmark_alignment", "R11_signal_input_cutoff", "R12_frozen_universe_selection_bias"]
VERDICTS = ("present", "assumption_only", "missing")
AVAILABILITY = ("retrospective_capture_2026", "evidence_assembly_2026", "not_established", "historical_contemporaneous")
START, END = "2023-09-04", "2025-03-31"
GUARD_LOG: list[dict] = []


# ---------------------------------------------------------------------------- guards
def _deny(kind: str, detail: str) -> None:
    GUARD_LOG.append({"kind": kind, "detail": detail})
    raise RuntimeError(f"denied by M4-03A validator guard: {kind}: {detail}")


def _is_write_mode(mode, flags) -> bool:
    if isinstance(mode, str):
        return any(ch in mode for ch in "wax+")
    if isinstance(flags, int):
        return bool(flags & (os.O_WRONLY | os.O_RDWR | os.O_APPEND | os.O_CREAT | os.O_TRUNC))
    return False


def _audit(event: str, args: tuple) -> None:
    if event == "open":
        path, mode, flags = args[0], args[1] if len(args) > 1 else None, args[2] if len(args) > 2 else None
        if _is_write_mode(mode, flags):
            try:
                target = Path(os.fsdecode(path)).resolve() if not isinstance(path, int) else None
            except Exception:  # noqa: BLE001
                target = None
            if target is None or ALLOWED_WRITE_ROOT not in (target, *target.parents):
                _deny("write_outside_claude_03a", f"{path!r} mode={mode!r} flags={flags!r}")
    elif event == "sqlite3.connect":
        _deny("sqlite", repr(args[:1]))
    elif event.startswith("socket.") and event != "socket.__new__":
        _deny("network", f"{event} {args[:1]!r}")
    elif event in ("subprocess.Popen", "os.system", "os.posix_spawn", "os.exec", "os.spawn", "os.fork"):
        _deny("subprocess", f"{event} {args[:1]!r}")


def _install_guards() -> None:
    sqlite3.connect = lambda *a, **k: _deny("sqlite", "sqlite3.connect monkeypatch")  # type: ignore[assignment]

    class _DeniedSocket(socket.socket):
        def __init__(self, *a, **k):
            _deny("network", "socket.socket construction")

    socket.socket = _DeniedSocket  # type: ignore[misc,assignment]
    socket.create_connection = lambda *a, **k: _deny("network", "socket.create_connection")  # type: ignore[assignment]
    subprocess.Popen = lambda *a, **k: _deny("subprocess", "subprocess.Popen monkeypatch")  # type: ignore[assignment,misc]
    subprocess.run = lambda *a, **k: _deny("subprocess", "subprocess.run monkeypatch")  # type: ignore[assignment]
    os.system = lambda *a, **k: _deny("subprocess", "os.system monkeypatch")  # type: ignore[assignment]
    sys.addaudithook(_audit)


def _self_check_guards() -> dict:
    probe_path = PROJECT / "m4_03a_guard_probe_should_not_exist.tmp"
    probes = {"sqlite3.connect(':memory:')": lambda: sqlite3.connect(":memory:"), "socket.socket": lambda: socket.socket(),
              "subprocess.run": lambda: subprocess.run([sys.executable, "-c", "pass"]), "os.system": lambda: os.system("echo probe"),
              "write_outside_claude_03a": lambda: open(probe_path, "w", encoding="utf-8")}
    outcome = {}
    for name, probe in probes.items():
        try:
            probe()
            outcome[name] = "NOT DENIED"
        except Exception as exc:  # noqa: BLE001
            outcome[name] = "denied" if "denied by M4-03A validator guard" in str(exc) else f"other_error:{exc}"
    outcome["probe_file_created"] = probe_path.exists()
    inside = EVIDENCE / "guard_probe_inside_claude_03a.txt"
    inside.write_text("write inside claude_03a allowed\n", encoding="utf-8")
    outcome["write_inside_claude_03a"] = "allowed" if inside.exists() else "FAILED"
    return outcome


# ---------------------------------------------------------------------------- helpers
def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def strict_eligible(availability: str, verdict: str) -> bool:
    """The matrix classifier: strict historical execution needs contemporaneous evidence that is present."""
    return verdict == "present" and availability == "historical_contemporaneous"


def check(problems: list[str], ok: bool, label: str) -> bool:
    if not ok:
        problems.append(label)
    return ok


# ---------------------------------------------------------------------------- synthetic kernel cases
def kernel_cases(k) -> dict:
    """Tiny synthetic cases through the frozen kernel.  Values are the SYN_CODEX_01 fixture shape (synthetic=True)."""
    S = "SYN_CODEX_01"
    T = "2024-03-19T09:30:00+08:00"
    sessions = ("2024-03-18", "2024-03-19", "2024-03-20", "2024-03-21")
    cal = k.SessionCalendar(sessions, "+08:00", "09:30", "15:00", "syn:calendar", "2024-01-01T00:00:00+08:00", True)
    fees = k.FeeSchedule("HYPOTHETICAL_FIXTURE", "1", "hypothetical_fixture", "syn:fees", "2024-01-01", None, ("syn_main",), "0.0003", "0.0003", "5.00", "0.00001", "0.0005")
    asm = k.ExecutionAssumptions("HYPOTHETICAL_FIXTURE", "hypothetical_fixture", "syn:policy", "0", "1", "0.01", k.LotPolicy("syn:lot", 100, 100, 100, "whole_odd_remainder_only", 1000000), k.SettlementPolicy("syn:T+1", 1))
    base = dict(
        decision=k.Decision("D", S, "buy", sessions[0], "2024-03-18T16:00:00+08:00", (k.InputAvailability("prior_close", "2024-03-18T15:05:00+08:00", "syn:prior_close"),), "syn:rule"),
        order=k.Order("O", "D", S, "buy", 100, "10.00", "2024-03-19T09:00:00+08:00", T, 1, "open_auction"),
        instrument=k.Instrument(S, "stock", "syn_main", "syn:listing", "syn:calendar", True), calendar=cal,
        tradability=k.TradabilityEvidence(S, sessions[1], "tradable", "none", "band", "11.00", "9.00", "not_st", "seasoned", T, T, "syn:tradable", True),
        price=k.PriceObservation(S, "10.00", "open_auction_print", T, T, "syn:price", "contemporaneous", True),
        capacity=k.LiquidityCapacity(S, "C", 1000, "share", "auction_matched_quantity", T, T, "syn:capacity", "contemporaneous", True),
        account=k.AccountState("SYN_ACCOUNT", "10000.00", (), "2024-03-19T09:00:00+08:00", True), fee_schedule=fees, assumptions=asm,
        attempt=k.ExecutionAttempt("A", T, sessions[1], "open_auction"),
    )
    CAPTURE = "2026-09-09T17:12:13.572989+00:00"     # the real audit's observed_at_min, used only as a synthetic instant

    def run(**over):
        rec = k.execute(k.ExecutionRequest(**{**base, **over})).record
        return {"status": rec["status"], "reasons": [r["code"] for r in rec["reasons"]], "evidence_grade": (rec.get("evidence") or {}).get("evidence_grade"),
                "assumptions_used": (rec.get("evidence") or {}).get("assumptions_used"), "filled": (rec.get("fill") or {}).get("filled_quantity")}

    cases = {}
    cases["control_contemporaneous_fill"] = run()
    cases["absent_capacity_stays_ineligible"] = run(capacity=None)
    cases["capture_instant_price_not_contemporaneous"] = run(price=k.PriceObservation(S, "10.00", "open", T, CAPTURE, "syn:daily_bar_captured_2026", "contemporaneous", True))
    cases["capture_instant_decision_input_not_available"] = run(decision=k.Decision("D", S, "buy", sessions[0], "2024-03-18T16:00:00+08:00", (k.InputAvailability("daily_close_captured_2026", CAPTURE, "syn:row_evidence.observed_at"),), "syn:rule"))
    cases["capture_instant_calendar_not_available"] = run(calendar=k.SessionCalendar(sessions, "+08:00", "09:30", "15:00", "syn:calendar", CAPTURE, True))
    cases["assumed_open_print_keeps_label"] = run(price=k.PriceObservation(S, "10.00", "open", T, CAPTURE, "syn:daily_bar_captured_2026", "predeclared_assumption", True, "ASSUMPTION:daily_bar_open_equals_0930_auction_print"))
    cases["unknown_st_without_declared_assumption"] = run(tradability=k.TradabilityEvidence(S, sessions[1], "tradable", "none", "band", "11.00", "9.00", "unknown", "seasoned", T, T, "syn:tradable", True))
    asm_st = k.ExecutionAssumptions("HYPOTHETICAL_FIXTURE_ST", "hypothetical_fixture", "syn:policy", "0", "1", "0.01", k.LotPolicy("syn:lot", 100, 100, 100, "whole_odd_remainder_only", 1000000), k.SettlementPolicy("syn:T+1", 1), (("st_status", "not_st"),))
    cases["unknown_st_with_declared_assumption_keeps_label"] = run(tradability=k.TradabilityEvidence(S, sessions[1], "tradable", "none", "band", "11.00", "9.00", "unknown", "seasoned", T, T, "syn:tradable", True), assumptions=asm_st)
    cases["assumed_capacity_keeps_label"] = run(capacity=k.LiquidityCapacity(S, "C", 1000, "share", "hypothetical_participation_of_full_day_volume", T, T, "syn:daily_volume", "predeclared_assumption", True, 0, "ASSUMPTION:hypothetical_capacity_not_opening_evidence"))
    expectations = {
        "control_contemporaneous_fill": lambda c: c["status"] == "filled" and c["evidence_grade"] == "contemporaneous" and c["filled"] == 100,
        "absent_capacity_stays_ineligible": lambda c: c["status"] == "unfilled" and "capacity_unproven" in c["reasons"] and not c["filled"],
        "capture_instant_price_not_contemporaneous": lambda c: c["status"] == "rejected" and "evidence_available_after_execution" in c["reasons"],
        "capture_instant_decision_input_not_available": lambda c: c["status"] == "rejected" and "input_not_available_at_decision" in c["reasons"],
        "capture_instant_calendar_not_available": lambda c: c["status"] == "rejected" and "calendar_not_available" in c["reasons"],
        "assumed_open_print_keeps_label": lambda c: c["status"] == "filled" and c["evidence_grade"] == "assumed" and any(a.startswith("price:ASSUMPTION:") for a in c["assumptions_used"]),
        "unknown_st_without_declared_assumption": lambda c: c["status"] == "rejected" and "unknown_state" in c["reasons"],
        "unknown_st_with_declared_assumption_keeps_label": lambda c: c["status"] == "filled" and c["evidence_grade"] == "assumed" and any(a.startswith("st_status:not_st:") for a in c["assumptions_used"]),
        "assumed_capacity_keeps_label": lambda c: c["status"] == "filled" and c["evidence_grade"] == "assumed" and any(a.startswith("capacity:ASSUMPTION:") for a in c["assumptions_used"]),
    }
    out = {}
    for name, result in cases.items():
        out[name] = {**result, "passed": bool(expectations[name](result))}
    return out


# ---------------------------------------------------------------------------- full-chain causal mapping cases (delivery 02)
def full_chain_cases(k, p, r, pm) -> dict:
    """proposal_mapping.py through the frozen risk layer, ledger and kernel on synthetic bars (SYN symbols, synthetic=True)."""
    from decimal import Decimal
    S, IDX = "SYN_03B_A", "SYN_03B_INDEX"
    CAPTURED = "2026-09-09T17:12:13.572989+00:00"          # the audit's observed_at_min, used only as a synthetic capture instant
    SESS = ("2024-03-18", "2024-03-19", "2024-03-20", "2024-03-21", "2024-03-22", "2024-03-25", "2024-03-26", "2024-03-27", "2024-03-28", "2024-03-29")
    BARS_A = {"2024-03-18": ("9.90", "10.10", "9.80", "10.00", 800000), "2024-03-19": ("10.05", "10.40", "9.90", "10.30", 1000000),
              "2024-03-20": ("10.20", "10.25", "9.40", "9.50", 900000), "2024-03-21": ("9.40", "9.60", "9.30", "9.45", 700000),
              "2024-03-22": ("9.50", "9.70", "9.40", "9.60", 600000), "2024-03-25": ("9.60", "9.80", "9.50", "9.70", 600000),
              "2024-03-26": ("9.70", "9.90", "9.60", "9.80", 600000), "2024-03-27": ("9.80", "10.00", "9.70", "9.90", 600000),
              "2024-03-28": ("9.90", "10.10", "9.80", "10.00", 600000), "2024-03-29": ("10.10", "10.30", "10.00", "10.20", 600000)}
    BARS_B = dict(BARS_A)                                       # same opens up to 03-19, different FUTURE suffix
    BARS_B["2024-03-19"] = ("10.05", "11.00", "9.50", "11.00", 5000000)   # close at the assumed band top; volume x5
    BARS_B["2024-03-20"] = ("11.50", "12.00", "11.00", "11.80", 5000000)
    BENCH = {"2024-03-18": "3000.00", "2024-03-28": "2970.00"}
    fees = pm.fee_schedule(k)
    policy = r.RiskPolicy("HYPOTHETICAL_03B_POLICY", "hypothetical_fixture", "0.05", "0.60", "0", "0.05", "0.10", 20, 5, 0, "0.02", 1,
                          ("stop_loss", "profit_target", "max_holding"), entry_phase="open_auction", exit_phase="open_auction")

    def engine(variant):
        cal = pm.calendar(k, SESS, CAPTURED, variant, True, "syn:calendar")
        asm = pm.execution_assumptions(k, declare_unknown_states=(variant == "assumed"))
        ledger = p.PortfolioLedger(k, ledger_id="SYN-03B-L", account_ref="SYN-03B-A", initial_cash="100000.00")
        eng = r.PolicyEngine(kernel=k, ledger_module=p, ledger=ledger, policy=policy, universe=(r.UniverseMember(S, "stock", "main", "syn:listing"),), benchmark_symbol=IDX, engine_id="SYN-03B-E")
        return eng, ledger, cal, asm

    def decide(eng, cal, asm, variant, session, bars, with_signal, did):
        ctx = pm.decision_context(r, session, cal, fees, asm)
        marks = (pm.mark(r, S, session, bars[session][3], CAPTURED, variant, True),)
        bench = (pm.benchmark_level(r, IDX, session, BENCH[session], CAPTURED, variant, True),) if session in BENCH else ()
        sigs = (pm.signal(r, f"SIG-{session}", S, session, CAPTURED, variant, True),) if with_signal else ()
        return eng.decide(did, ctx, marks=marks, signals=sigs, benchmark=bench), ctx

    LAST_EVIDENCE = {}

    def attempt(eng, ctx, iid, session, bars, variant, cap_variant, qty, aid):
        prev = SESS[SESS.index(session) - 1]
        inputs = pm.OpenAttemptInputs(S, session, bars[session][0], bars[prev][3], False, CAPTURED, "main", 200)
        ev = pm.attempt_evidence(k, r, inputs, aid, variant, cap_variant, qty, True)
        dry_run(eng, ctx, iid, aid, ev, qty)
        return eng.execute(iid, ctx, ev)

    def dry_run(eng, ctx, iid, aid, ev, qty):
        """State-free kernel dry run of the identical request BEFORE the engine applies it (the frozen engine's own request
        builder, pre-fill account state); its result_hash is later compared with the ledger's recorded kernel result_hash."""
        if ev.price.available_at > ev.executed_at:          # raw variant: the risk layer refuses before the kernel; no dry run possible
            LAST_EVIDENCE[(id(eng), iid, aid)] = None
            return
        rec = k.execute(eng._request(eng.intents()[iid], ctx, ev, qty)).record
        LAST_EVIDENCE[(id(eng), iid, aid)] = rec

    def kernel_evidence(eng, ctx, iid, aid, x):
        rec = LAST_EVIDENCE[(id(eng), iid, aid)]
        same = rec["result_hash"] == ((x.get("ledger_record") or {}).get("kernel") or {}).get("result_hash")
        return {**rec["evidence"], "result_hash_matches_ledger": same, "price_source_ref": rec["evidence"]["price"]["source_ref"]}

    out = {}

    def run_assumed(bars, cap_variant="full_fill"):
        eng, ledger, cal, asm = engine("assumed")
        d1, ctx1 = decide(eng, cal, asm, "assumed", "2024-03-18", bars, True, "D1")
        x1 = attempt(eng, ctx1, "D1:buy:SYN_03B_A", "2024-03-19", bars, "assumed", cap_variant, 400, "X1")
        return eng, ledger, cal, asm, d1, ctx1, x1

    # ---- assumed smoke: entry -> hold -> stop -> exit fill -> cooldown -> re-entry -> performance (hand-calculated) ----
    eng, ledger, cal, asm, d1, ctx1, x1 = run_assumed(BARS_A)
    e1 = d1["entries"][0]
    d2, _ = decide(eng, cal, asm, "assumed", "2024-03-19", BARS_A, False, "D2")
    d3, ctx3 = decide(eng, cal, asm, "assumed", "2024-03-20", BARS_A, False, "D3")
    x2 = attempt(eng, ctx3, "D3:sell:SYN_03B_A", "2024-03-21", BARS_A, "assumed", "full_fill", 400, "X2")
    cool = [decide(eng, cal, asm, "assumed", s, BARS_A, True, f"D-{s}")[0] for s in ("2024-03-22", "2024-03-25", "2024-03-26", "2024-03-27")]
    d8, ctx8 = decide(eng, cal, asm, "assumed", "2024-03-28", BARS_A, True, "D8")
    perf = eng.performance(ctx8, marks=(pm.mark(r, S, "2024-03-28", BARS_A["2024-03-28"][3], CAPTURED, "assumed", True),),
                           benchmark=(pm.benchmark_level(r, IDX, "2024-03-18", BENCH["2024-03-18"], CAPTURED, "assumed", True), pm.benchmark_level(r, IDX, "2024-03-28", BENCH["2024-03-28"], CAPTURED, "assumed", True)),
                           start_session="2024-03-18", initial_cash="100000.00")
    o1, o2 = x1["outcome"], x2["outcome"]
    kev = kernel_evidence(eng, ctx1, "D1:buy:SYN_03B_A", "X1", x1)
    out["assumed_full_chain_smoke"] = {
        "d1_entry": {"quantity": e1.get("quantity"), "reserved_budget": e1.get("reserved_budget"), "estimated_cost": e1.get("estimated_cost"), "limit_price": e1.get("limit_price"), "mark_source_ref": e1.get("mark_evidence", {}).get("source_ref")},
        "x1": {"status": x1["status"], "filled": o1.get("filled_quantity"), "fill_price": o1.get("fill_price"), "cash_after": o1.get("cash_after"), "fees": o1.get("fees"),
               "ledger_evidence_grade": (x1.get("ledger_record") or {}).get("kernel", {}).get("evidence_grade"), "kernel_result_hash_matches_ledger": kev["result_hash_matches_ledger"],
               "evidence_grade": kev.get("evidence_grade"), "assumptions_used": kev.get("assumptions_used"), "assumed_states": kev.get("assumed_states"),
               "price_source_ref": kev.get("price_source_ref"), "tradability_limit_state": (kev.get("tradability") or {}).get("limit_state"), "band": ((kev.get("tradability") or {}).get("limit_down_price"), (kev.get("tradability") or {}).get("limit_up_price"))},
        "d2_hold": {"decision": d2["exits"][0]["decision"], "equity": d2["valuation"]["equity"], "entry_cost_reference": d2["valuation"]["positions"][S]["entry_cost_reference"]},
        "d3_exit": {"decision": d3["exits"][0]["decision"], "reason": d3["exits"][0].get("reason"), "limit_price": d3["exits"][0].get("limit_price")},
        "x2": {"status": x2["status"], "filled": o2.get("filled_quantity"), "fill_price": o2.get("fill_price"), "cash_after": o2.get("cash_after"), "cooldown_started_session": o2.get("cooldown_started_session")},
        "cooldown_refusals": [c["entries"][0]["reason"] for c in cool], "d8_reentry": {"decision": d8["entries"][0]["decision"], "quantity": d8["entries"][0].get("quantity"), "reserved_budget": d8["entries"][0].get("reserved_budget")},
        "performance": {"equity": perf["equity"], "return": perf["return"], "realized_pnl_total": perf["realized_pnl_total"], "benchmark_return": perf["benchmark"]["return"], "status": perf["status"]},
        "positions_after": ledger.positions(), "ledger_reconcile_ok": ledger.reconcile()["ok"],
    }
    s = out["assumed_full_chain_smoke"]
    s["passed"] = (
        s["d1_entry"] == {"quantity": 400, "reserved_budget": "5000.00", "estimated_cost": "4014.08", "limit_price": "10.20", "mark_source_ref": f"MODEL:daily_bar_cache.close; captured={CAPTURED}; assumptions={pm.ASSUMPTIONS['close_availability']}"}
        and s["x1"]["status"] == "filled" and s["x1"]["filled"] == 400 and s["x1"]["fill_price"] == "10.08" and s["x1"]["cash_after"] == "95961.92" and s["x1"]["fees"]["total"] == "6.08"
        and s["x1"]["evidence_grade"] == "assumed" and s["x1"]["ledger_evidence_grade"] == "assumed" and s["x1"]["kernel_result_hash_matches_ledger"] and s["x1"]["tradability_limit_state"] == "none" and s["x1"]["band"] == ("9.00", "11.00")
        and set(a.split(":")[0] for a in s["x1"]["assumptions_used"]) == {"price", "capacity", "st_status", "listing_state"}
        and f"captured={CAPTURED}" in s["x1"]["price_source_ref"] and pm.ASSUMPTIONS["open_print"] in s["x1"]["price_source_ref"]
        and s["d2_hold"] == {"decision": "hold", "equity": "100081.92", "entry_cost_reference": "10.0952"}
        and s["d3_exit"] == {"decision": "exit", "reason": "stop_loss", "limit_price": "9.31"}
        and s["x2"] == {"status": "filled", "filled": 400, "fill_price": "9.38", "cash_after": "99704.84", "cooldown_started_session": "2024-03-21"}
        and s["cooldown_refusals"] == ["cooldown_active"] * 4 and s["d8_reentry"] == {"decision": "buy", "quantity": 400, "reserved_budget": "4985.24"}
        and s["performance"] == {"equity": "99704.84", "return": "-0.002952", "realized_pnl_total": "-295.16", "benchmark_return": "-0.010000", "status": "valued"}
        and s["positions_after"] == {} and s["ledger_reconcile_ok"] is True)

    # ---- strict-raw: raw capture instants everywhere -> refused at the decision stage; no intent exists ----------------
    eng_r, ledger_r, cal_r, asm_r = engine("raw")
    d1r, _ = decide(eng_r, cal_r, asm_r, "raw", "2024-03-18", BARS_A, True, "D1")
    out["strict_raw_decision_refusal"] = {"status": d1r["status"], "refusal_codes": sorted({x["code"] for x in d1r["refusals"]}), "refused_what": sorted({x.get("what") for x in d1r["refusals"]}),
                                          "entries": d1r.get("entries"), "intents": len(eng_r.intents()), "ledger_records": len(ledger_r.records)}
    o = out["strict_raw_decision_refusal"]
    o["passed"] = o["status"] == "decided" and o["refusal_codes"] == ["future_evidence"] and o["refused_what"] == ["benchmark", "mark", "signal"] and o["entries"] == [] and o["intents"] == 0 and o["ledger_records"] == 0
    # ---- evidence-eligibility refusal at the attempt: assumed decision, raw attempt evidence -> future_evidence, intent untouched ----
    eng_m, ledger_m, cal_m, asm_m = engine("assumed")
    d1m, ctx1m = decide(eng_m, cal_m, asm_m, "assumed", "2024-03-18", BARS_A, True, "D1")
    before = eng_m.intents()
    xr = attempt(eng_m, ctx1m, "D1:buy:SYN_03B_A", "2024-03-19", BARS_A, "raw", "full_fill", 400, "X1")
    out["raw_attempt_after_assumed_decision"] = {"status": xr["status"], "reason": xr.get("reason"), "intents_unchanged": eng_m.intents() == before, "reservation": eng_m.reservations()["reserved_cash"], "ledger_records": len(ledger_m.records)}
    o = out["raw_attempt_after_assumed_decision"]
    o["passed"] = o["status"] == "refused" and o["reason"] == "future_evidence" and o["intents_unchanged"] and o["reservation"] == "5000.00" and o["ledger_records"] == 0
    # ---- capacity-removal sensitivity of the assumed chain (NOT a strict path): capacity_unproven, no fill, expired ----
    eng_c, ledger_c, cal_c, asm_c, d1c, ctx1c, x1c = run_assumed(BARS_A, cap_variant="none")
    lr = x1c.get("ledger_record") or {}
    out["assumed_capacity_removed_sensitivity"] = {"status": x1c["status"], "kernel_status": (lr.get("kernel") or {}).get("status"), "kernel_reasons": [q["code"] for q in (lr.get("kernel") or {}).get("reasons", [])],
                                                   "ledger_status": lr.get("status"), "cash": ledger_c.snapshot()["cash"], "positions": ledger_c.positions(), "reservation_after": eng_c.reservations()["reserved_cash"]}
    o = out["assumed_capacity_removed_sensitivity"]
    o["passed"] = o["status"] == "expired" and o["kernel_status"] == "unfilled" and o["kernel_reasons"] == ["capacity_unproven"] and o["ledger_status"] == "no_effect" and o["cash"] == "100000.00" and o["positions"] == {} and o["reservation_after"] == "0.00"

    # ---- future-suffix invariance: bars B differ from 03-19 high/low/close/volume onward; D1 and X1 records identical ----
    eng_b, ledger_b, cal_b, asm_b, d1b, ctx1b, x1b = run_assumed(BARS_B)
    d2b, _ = decide(eng_b, cal_b, asm_b, "assumed", "2024-03-19", BARS_B, False, "D2")
    kev_b = kernel_evidence(eng_b, ctx1b, "D1:buy:SYN_03B_A", "X1", x1b)
    out["future_suffix_invariance"] = {"d1_hash_equal": d1["record_hash"] == d1b["record_hash"], "x1_hash_equal": x1["record_hash"] == x1b["record_hash"],
                                       "x1_filled_both": (x1["outcome"].get("filled_quantity"), x1b["outcome"].get("filled_quantity")),
                                       "limit_state_both": (kev["tradability"]["limit_state"], kev_b["tradability"]["limit_state"]),
                                       "kernel_result_hash_equal": kev["result_hash_matches_ledger"] and kev_b["result_hash_matches_ledger"]
                                       and (x1["ledger_record"]["kernel"]["result_hash"] == x1b["ledger_record"]["kernel"]["result_hash"]),
                                       "d2_diverges_after_close_available": d2["record_hash"] != d2b["record_hash"], "d2_equity_a_b": (d2["valuation"]["equity"], d2b["valuation"]["equity"])}
    o = out["future_suffix_invariance"]
    o["passed"] = o["d1_hash_equal"] and o["x1_hash_equal"] and o["kernel_result_hash_equal"] and o["x1_filled_both"] == (400, 400) and o["limit_state_both"] == ("none", "none") and o["d2_diverges_after_close_available"] and o["d2_equity_a_b"] == ("100081.92", "100361.92")

    # ---- limit_state from the open print only (band from previous close 10.00 main: 9.00 / 11.00) ------------------------
    lim = {}
    for name, bars, side_expect in (("open_at_band_top_buy_unfilled", {**BARS_A, "2024-03-19": ("11.00", "11.00", "11.00", "11.00", 100)}, ("expired", "limit_up_no_buy_fill")),
                                    ("open_at_band_bottom_buy_fills", {**BARS_A, "2024-03-19": ("9.00", "9.00", "9.00", "9.00", 100)}, ("filled", None))):
        eng_l, ledger_l, cal_l, asm_l, d1l, ctx1l, x1l = run_assumed(bars)
        lr = x1l.get("ledger_record") or {}
        kev_l = kernel_evidence(eng_l, ctx1l, "D1:buy:SYN_03B_A", "X1", x1l)
        lim[name] = {"status": x1l["status"], "kernel_reasons": [q["code"] for q in (lr.get("kernel") or {}).get("reasons", [])], "limit_state": kev_l["tradability"]["limit_state"],
                     "band": (kev_l["tradability"]["limit_down_price"], kev_l["tradability"]["limit_up_price"]), "filled": x1l["outcome"].get("filled_quantity"),
                     "kernel_result_hash_matches_ledger": kev_l["result_hash_matches_ledger"]}
        lim[name]["passed"] = (lim[name]["status"] == side_expect[0] and lim[name]["band"] == ("9.00", "11.00") and lim[name]["kernel_result_hash_matches_ledger"]
                               and lim[name]["limit_state"] == ("limit_up" if side_expect[1] else "limit_down")
                               and ((side_expect[1] in lim[name]["kernel_reasons"]) if side_expect[1] else lim[name]["filled"] == 400))
    out["limit_state_from_open_only"] = {**lim, "passed": all(v["passed"] for v in lim.values())}
    out["limit_state_pure"] = {"open_11.00": pm.limit_state_from_open(Decimal("11.00"), Decimal("9.00"), Decimal("11.00")), "open_9.00": pm.limit_state_from_open(Decimal("9.00"), Decimal("9.00"), Decimal("11.00")),
                               "open_10.05": pm.limit_state_from_open(Decimal("10.05"), Decimal("9.00"), Decimal("11.00")), "band_bse_from_10.00": tuple(str(x) for x in pm.assumed_band(Decimal("10.00"), "bse"))}
    out["limit_state_pure"]["passed"] = out["limit_state_pure"]["open_11.00"] == "limit_up" and out["limit_state_pure"]["open_9.00"] == "limit_down" and out["limit_state_pure"]["open_10.05"] == "none" and out["limit_state_pure"]["band_bse_from_10.00"] == ("7.00", "13.00")

    # ---- capacity model consistency at the kernel (participation 1.0): 100 / 400 full fill, cumulative exhaustion, fixed 5000 partial ----
    T = "2024-03-19T09:30:00+08:00"
    cal_k = pm.calendar(k, SESS, CAPTURED, "assumed", True, "syn:calendar")
    asm_k = pm.execution_assumptions(k)

    def kreq(qty, cap_variant, consumed=0, cash="200000.00"):
        inputs = pm.OpenAttemptInputs(S, "2024-03-19", "10.05", "10.00", False, CAPTURED, "main", 200)
        ev = pm.attempt_evidence(k, r, inputs, "K1", "assumed", cap_variant, qty, True)
        cap = ev.capacity if consumed == 0 else k.LiquidityCapacity(S, ev.capacity.capacity_id, ev.capacity.quantity, "share", ev.capacity.basis, ev.capacity.observed_at, ev.capacity.available_at,
                                                                    ev.capacity.source_ref, "predeclared_assumption", True, consumed, ev.capacity.assumption_ref)
        req = k.ExecutionRequest(decision=k.Decision("D", S, "buy", "2024-03-18", "2024-03-18T16:00:00+08:00", (k.InputAvailability("close", "2024-03-18T16:00:00+08:00", "syn:close"),), "syn:rule"),
                                 order=k.Order("O", "D", S, "buy", qty, "10.20", "2024-03-18T16:00:00+08:00", T, 1, "open_auction"),
                                 instrument=k.Instrument(S, "stock", "main", "syn:listing", cal_k.source_ref, True), calendar=cal_k, tradability=ev.tradability, price=ev.price,
                                 account=k.AccountState("SYN-03B-A", cash, (), "2024-03-19T09:00:00+08:00", True), fee_schedule=fees, assumptions=asm_k,
                                 attempt=k.ExecutionAttempt("K1", T, "2024-03-19", "open_auction"), capacity=cap)
        rec = k.execute(req).record
        return {"status": rec["status"], "reasons": [q["code"] for q in rec["reasons"]], "filled": rec["fill"]["filled_quantity"], "remaining": rec["fill"].get("remaining_quantity"),
                "allowance": (rec["fill"].get("capacity") or {}).get("allowance_quantity"), "consumed_after": (rec["fill"].get("capacity") or {}).get("consumed_after"), "grade": rec["evidence"]["evidence_grade"]}

    capc = {"full_fill_100": kreq(100, "full_fill"), "full_fill_400": kreq(400, "full_fill"), "full_fill_400_same_capacity_id_consumed_400": kreq(400, "full_fill", consumed=400),
            "fixed_5000_order_9900_partial": kreq(9900, "fixed_5000"), "fixed_5000_order_400_full": kreq(400, "fixed_5000")}
    capc["passed"] = (capc["full_fill_100"]["status"] == "filled" and capc["full_fill_100"]["filled"] == 100 and capc["full_fill_100"]["allowance"] == 100
                      and capc["full_fill_400"]["status"] == "filled" and capc["full_fill_400"]["filled"] == 400 and capc["full_fill_400"]["allowance"] == 400
                      and capc["full_fill_400_same_capacity_id_consumed_400"]["status"] == "unfilled" and "capacity_exhausted" in capc["full_fill_400_same_capacity_id_consumed_400"]["reasons"]
                      and capc["fixed_5000_order_9900_partial"]["status"] == "partially_filled" and capc["fixed_5000_order_9900_partial"]["filled"] == 5000 and capc["fixed_5000_order_9900_partial"]["remaining"] == 4900
                      and capc["fixed_5000_order_400_full"]["status"] == "filled" and capc["fixed_5000_order_400_full"]["filled"] == 400
                      and all(v["grade"] == "assumed" for v in capc.values() if isinstance(v, dict)))
    out["capacity_model_consistency"] = capc

    # ---- halt session: placeholder price cannot fill; status suspended; intent stays live/expired per kernel -------------
    eng_h, ledger_h, cal_h, asm_h = engine("assumed")
    d1h, ctx1h = decide(eng_h, cal_h, asm_h, "assumed", "2024-03-18", BARS_A, True, "D1")
    inputs_h = pm.OpenAttemptInputs(S, "2024-03-19", None, "10.00", True, CAPTURED, "main", 200)
    ev_h = pm.attempt_evidence(k, r, inputs_h, "XH", "assumed", "full_fill", 400, True)
    dry_run(eng_h, ctx1h, "D1:buy:SYN_03B_A", "XH", ev_h, 400)
    xh = eng_h.execute("D1:buy:SYN_03B_A", ctx1h, ev_h)
    lr = xh.get("ledger_record") or {}
    kev_h = kernel_evidence(eng_h, ctx1h, "D1:buy:SYN_03B_A", "XH", xh)
    out["halt_session_placeholder_cannot_fill"] = {"status": xh["status"], "kernel_status": (lr.get("kernel") or {}).get("status"), "kernel_reasons": [q["code"] for q in (lr.get("kernel") or {}).get("reasons", [])],
                                                   "price_field": kev_h["price"]["field"], "tradability_status": kev_h["tradability"]["status"], "kernel_result_hash_matches_ledger": kev_h["result_hash_matches_ledger"],
                                                   "positions": ledger_h.positions(), "cash": ledger_h.snapshot()["cash"]}
    o = out["halt_session_placeholder_cannot_fill"]
    o["passed"] = (o["kernel_status"] == "unfilled" and o["kernel_reasons"] == ["suspended"] and o["price_field"] == "previous_close_placeholder_no_print" and o["tradability_status"] == "suspended"
                   and o["kernel_result_hash_matches_ledger"] and o["positions"] == {} and o["cash"] == "100000.00")

    # ---- ex-date post-hoc flag: pure, changes no record --------------------------------------------------------------------
    flagged = pm.ex_date_flags([{"symbol": S, "entry_session": "2024-03-19", "last_session": "2024-03-21", "realized_pnl": "-295.16"}], {S: ["2024-03-20"]})
    clean = pm.ex_date_flags([{"symbol": S, "entry_session": "2024-03-19", "last_session": "2024-03-21", "realized_pnl": "-295.16"}], {S: ["2024-03-25"]})
    out["ex_date_post_hoc_flag"] = {"flagged": flagged[0]["known_ex_dates_in_window"], "flag": flagged[0]["flag"], "clean_flag": clean[0]["flag"], "adjustment_uncertainty_always": flagged[0]["adjustment_uncertainty"] and clean[0]["adjustment_uncertainty"],
                                    "pnl_unchanged": flagged[0]["realized_pnl"] == clean[0]["realized_pnl"] == "-295.16"}
    o = out["ex_date_post_hoc_flag"]
    o["passed"] = o["flagged"] == ["2024-03-20"] and o["flag"] == pm.ASSUMPTIONS["ex_date_flag"] and o["clean_flag"] is None and o["adjustment_uncertainty_always"] and o["pnl_unchanged"]
    return out


# ---------------------------------------------------------------------------- main
def main() -> int:
    started = datetime.now(timezone.utc).isoformat()
    EVIDENCE.mkdir(exist_ok=True)
    _install_guards()
    self_check = _self_check_guards()
    self_check_denials = list(GUARD_LOG)
    GUARD_LOG.clear()
    problems: list[str] = []
    q = json.loads((HERE / "qualification.json").read_text(encoding="utf-8"))

    # 1. pins -----------------------------------------------------------------------------------------------
    pins = {}
    check(problems, sha256(PROJECT / TASK_FILE) == TASK_SHA, "task_file_sha")
    for name, expected in FREEZES.items():
        got = sha256(M4 / name)
        pins[f"claude methods/_m4_20260912/{name}"] = {"expected": expected, "actual": got, "ok": got == expected}
        check(problems, got == expected, f"freeze:{name}")
        doc = json.loads((M4 / name).read_text(encoding="utf-8"))
        check(problems, doc["M4_complete"] is False and doc["review_only"] is True and doc["live_trading_enabled"] is False and doc["training_eligible"] is False and doc["strict_pit"] is False, f"freeze_flags:{name}")
    for key, meta in q["pinned_sources"].items():
        p = PROJECT / meta["path"]
        got = sha256(p) if p.is_file() else None
        pins[meta["path"]] = {"expected": meta["sha256"], "actual": got, "ok": got == meta["sha256"]}
        check(problems, got == meta["sha256"], f"pin:{key}")
    databases = {}
    for key, meta in q["candidate_databases"].items():
        p = PROJECT / meta["path"]
        st = p.stat()
        got = sha256(p)
        sidecars = {sfx: (PROJECT / (meta["path"] + sfx)).exists() for sfx in ("-wal", "-shm", "-journal")}
        ok = got == meta["sha256"] and st.st_size == meta["bytes"] and not any(sidecars.values())
        databases[meta["path"]] = {"expected": meta["sha256"], "actual": got, "bytes": st.st_size, "mtime_ns": st.st_mtime_ns, "sidecars_present": sidecars, "ok": ok, "access": "hash/stat only"}
        check(problems, ok, f"database:{key}")

    # 2. coverage and explicit missing/unknown handling ---------------------------------------------------------
    rows = {r["id"]: r for r in q["requirements"]}
    check(problems, list(rows) == REQUIRED_ROWS, "required_rows_order_or_set")
    row_checks = {}
    for rid in REQUIRED_ROWS:
        r = rows.get(rid)
        if r is None:
            row_checks[rid] = "missing_row"
            continue
        issues = []
        if not r["evidence"] or not all(e.get("ref") and e.get("detail") and e.get("kind") in ("table", "metadata", "file", "code") for e in r["evidence"]):
            issues.append("evidence_refs")
        if not isinstance(r["development_coverage"], dict) or not r["development_coverage"]:
            issues.append("coverage")
        if r["availability_semantics"] not in AVAILABILITY:
            issues.append("availability_vocabulary")
        if r["verdict"] not in VERDICTS:
            issues.append("verdict_vocabulary")
        m = r["modes"]
        if set(m) != {"strict_historical_execution", "retrospective_bar_diagnostics", "hypothetical_execution_assumptions"}:
            issues.append("modes")
        else:
            strict_claimed = m["strict_historical_execution"].startswith("eligible")
            if strict_claimed != strict_eligible(r["availability_semantics"], r["verdict"]):
                issues.append("strict_mode_inconsistent_with_classifier")
            if r["verdict"] == "missing" and not m["hypothetical_execution_assumptions"].startswith(("assumption_required", "ineligible")):
                issues.append("missing_row_must_be_assumption_required_or_ineligible")
            if r["verdict"] == "present" and not m["retrospective_bar_diagnostics"].startswith("eligible"):
                issues.append("present_row_should_allow_retrospective_diagnostics")
            if r["verdict"] == "assumption_only" and not m["hypothetical_execution_assumptions"].startswith("eligible_with_label"):
                issues.append("assumption_only_row_must_be_labelled")
        if not r["consequence"].strip():
            issues.append("consequence")
        row_checks[rid] = issues or "ok"
        for i in issues:
            problems.append(f"row:{rid}:{i}")
    check(problems, all(r["availability_semantics"] != "historical_contemporaneous" for r in rows.values()), "no_row_may_claim_historical_contemporaneous_here")
    check(problems, q["summary"]["strict_historical_baseline_provable_now"] is False and q["summary"]["strict_historical_execution_eligible_requirements"] == [], "summary_strict_baseline_must_be_unprovable")

    # 3. anchors --------------------------------------------------------------------------------------------------
    anchor_checks = {}
    text_cache: dict[str, list[str]] = {}
    for name, a in q["source_anchors"].items():
        if a["path"] not in text_cache:
            text_cache[a["path"]] = (PROJECT / a["path"]).read_text(encoding="utf-8").splitlines()
        lines = text_cache[a["path"]]
        ok = 1 <= a["line"] <= len(lines) and a["contains"] in lines[a["line"] - 1]
        anchor_checks[name] = ok
        check(problems, ok, f"anchor:{name}")

    # 4. numbers recomputed from pinned metadata (no price rows) -------------------------------------------------
    audit = json.loads((PROJECT / q["pinned_sources"]["audit_result"]["path"]).read_text(encoding="utf-8"))
    index = json.loads((PROJECT / q["pinned_sources"]["metadata_index"]["path"]).read_text(encoding="utf-8"))
    qual = json.loads((PROJECT / q["pinned_sources"]["qualification_v2"]["path"]).read_text(encoding="utf-8"))
    pilot = list(csv.DictReader((PROJECT / q["pinned_sources"]["pilot_symbols"]["path"]).open(encoding="utf-8")))
    stocks = [s for s in audit["per_symbol"] if s["role"] == "stock"]
    instruments = {i["symbol"]: i for i in index["instruments"]}
    recomputed = {
        "development_sessions": len([d for d in index["calendar"]["sessions"] if START <= d <= END]),
        "stock_price_rows": sum(s["development_prices"] for s in stocks),
        "confirmed_full_day_halt_keys": sum(s["development_halts"] for s in stocks),
        "ledger_halt_keys_in_development": len([x for x in qual["suspension_ledger"] if START <= x["date"] <= END]),
        "index_rows": sum(s["development_prices"] for s in audit["per_symbol"] if s["role"] == "benchmark"),
        "stocks": len(stocks), "benchmarks": sum(1 for s in audit["per_symbol"] if s["role"] == "benchmark"),
        "stocks_with_250_warmup": sum(1 for s in stocks if s["warmup_prices"] >= 250),
        "known_ex_dates_inside_development": sum(1 for i in instruments.values() for e in i["known_cash_events"] if START <= e["ex_date"] <= END),
        "instruments_st_unknown": sum(1 for i in instruments.values() if i["historical_st_status"] == "unknown"),
        "instruments_ca_unknown": sum(1 for i in instruments.values() if i["corporate_action_completeness"] == "unknown"),
        "instruments_capture_not_original": sum(1 for i in instruments.values() if i["capture_time_is_original_market_availability"] is False),
        "source_name_invalid_rows": audit["source_name_status_counts"].get("invalid_source_name"),
        "observed_at_min": audit["observed_at_min"], "observed_at_max": audit["observed_at_max"],
        "original_historical_availability_proved": audit["original_historical_availability_proved"],
        "pilot_strata": dict(Counter(r["stratum"] for r in pilot)), "pilot_st_names_2026": sorted((r["symbol"], r["name"]) for r in pilot if "ST" in r["name"]),
        "unlisted_throughout_development": sorted(s["symbol"] for s in stocks if s["expected_development_sessions"] == 0),
    }
    f = q["facts"]
    expect = {
        "development_sessions": f["development_sessions"], "stock_price_rows": f["stock_price_rows"], "confirmed_full_day_halt_keys": f["confirmed_full_day_halt_keys"],
        "ledger_halt_keys_in_development": f["confirmed_full_day_halt_keys"], "index_rows": f["index_rows"], "stocks": f["pool"]["stocks"], "benchmarks": f["pool"]["benchmarks"],
        "stocks_with_250_warmup": f["warmup"]["stocks_with_250_bars_before_first_development_decision"], "known_ex_dates_inside_development": sum(len(v["inside_development"]) for v in f["known_cash_events"].values()),
        "instruments_st_unknown": 52, "instruments_ca_unknown": 52, "instruments_capture_not_original": 52, "source_name_invalid_rows": 27900,
        "observed_at_min": f["capture"]["observed_at_min"], "observed_at_max": f["capture"]["observed_at_max"], "original_historical_availability_proved": False,
        "pilot_strata": f["pilot_strata"], "pilot_st_names_2026": [tuple(x) for x in f["pilot_names_containing_ST_2026_only"]], "unlisted_throughout_development": f["pool"]["unlisted_throughout_development"],
    }
    number_checks = {k: recomputed[k] == expect[k] for k in expect}
    for k, ok in number_checks.items():
        check(problems, ok, f"number:{k}:{recomputed[k]!r}!={expect[k]!r}")
    funnel = q["eligibility_funnel_structural"]
    check(problems, funnel["strict_contemporaneous_execution_evidence_rows"] == 0 and funnel["phase_level_capacity_rows"] == 0 and funnel["sourced_fee_schedules"] == 0, "funnel_zero_strict_evidence")
    check(problems, funnel["price_keys"] == recomputed["stock_price_rows"] and funnel["confirmed_full_day_halt_keys"] == recomputed["confirmed_full_day_halt_keys"], "funnel_numbers")

    # 5. safety flags -----------------------------------------------------------------------------------------------
    s = q["safety"]
    check(problems, s["sqlite_connections"] == 0 and s["network_requests"] == 0 and s["historical_trades_run"] == 0 and s["price_rows_consumed"] == 0
          and s["review_only"] is True and s["live_trading_enabled"] is False and s["training_eligible"] is False and s["strict_pit"] is False and s["M4_complete"] is False and s["M5_started"] is False, "safety_flags")

    # 6. synthetic kernel cases (frozen kernel by file path; hash verified above as pin m4_execution) --------------
    kernel_path = PROJECT / q["pinned_sources"]["m4_execution"]["path"]
    k = load_module("m4_execution_frozen_for_03a_validator", kernel_path)
    check(problems, k.POLICY_HASH == "9bea83482d545e6f39dd8eb70e89d674dd5d900378b596c243da8e122c273e62", "kernel_policy_hash")
    synthetic = kernel_cases(k)
    for name, c in synthetic.items():
        check(problems, c["passed"], f"synthetic:{name}")
    classifier_cases = {
        "capture_2026_present_is_not_strict": strict_eligible("retrospective_capture_2026", "present") is False,
        "assembly_2026_present_is_not_strict": strict_eligible("evidence_assembly_2026", "present") is False,
        "not_established_missing_is_not_strict": strict_eligible("not_established", "missing") is False,
        "contemporaneous_present_would_be_strict": strict_eligible("historical_contemporaneous", "present") is True,
        "contemporaneous_but_missing_is_not_strict": strict_eligible("historical_contemporaneous", "missing") is False,
    }
    for name, ok in classifier_cases.items():
        check(problems, ok, f"classifier:{name}")
    # 7. delivery 02: causal mapping through the complete frozen chain -------------------------------------------
    ledger_mod = load_module("m4_portfolio_frozen_for_03a_validator", PROJECT / q["pinned_sources"]["m4_portfolio"]["path"])
    risk_mod = load_module("m4_risk_frozen_for_03a_validator", PROJECT / q["pinned_sources"]["m4_risk"]["path"])
    check(problems, ledger_mod.LEDGER_POLICY_HASH == "633f78d987141b0e3dccad5d8e711b241a2eaf58b2a8dbe65e57603b5624d6f6" and risk_mod.RISK_POLICY_HASH == "013f1580f9b6c08092281202f012a567a8f2c743815345c505afe8ebd220ffdf", "ledger_risk_policy_hashes")
    mapping = load_module("proposal_mapping_under_validation", HERE / "proposal_mapping.py")
    full_chain = full_chain_cases(k, ledger_mod, risk_mod, mapping)
    for name, c in full_chain.items():
        check(problems, bool(c.get("passed")), f"full_chain:{name}")
    check(problems, not any(name == "app" or name.startswith("app.") for name in sys.modules), "app_not_imported")
    check(problems, "conftest" not in sys.modules and "pytest" not in sys.modules, "conftest_pytest_not_imported")

    receipt = {
        "schema": "m4.claude_03a.validation_receipt.v1", "task_id": q["task_id"], "started_at_utc": started, "finished_at_utc": datetime.now(timezone.utc).isoformat(),
        "command": [sys.executable, "-B", "-X", "utf8", str(Path(__file__).resolve().relative_to(PROJECT).as_posix())],
        "qualification_sha256": sha256(HERE / "qualification.json"), "matrix_sha256": sha256(HERE / "QUALIFICATION_MATRIX.md"),
        "guards": {"self_check": self_check, "self_check_denials": self_check_denials, "denials_during_validation": list(GUARD_LOG), "bytecode_disabled": sys.dont_write_bytecode},
        "pins": pins, "candidate_databases": databases, "row_checks": row_checks, "anchor_checks": {"total": len(anchor_checks), "ok": sum(anchor_checks.values()), "failed": [n for n, ok in anchor_checks.items() if not ok]},
        "number_checks": {"recomputed": recomputed, "ok": all(number_checks.values()), "failed": [k for k, ok in number_checks.items() if not ok]},
        "synthetic_kernel_cases": synthetic, "classifier_cases": classifier_cases,
        "full_chain_cases": full_chain, "proposal_mapping_sha256": sha256(HERE / "proposal_mapping.py"),
        "frozen_engines": {"kernel_policy_hash": k.POLICY_HASH, "ledger_policy_hash": ledger_mod.LEDGER_POLICY_HASH, "risk_policy_hash": risk_mod.RISK_POLICY_HASH},
        "app_imported": any(name == "app" or name.startswith("app.") for name in sys.modules),
        "problems": problems, "passed": not problems,
        "safety": {"sqlite_connections": 0, "network_requests": 0, "historical_trades_run": 0, "price_rows_consumed": 0, "review_only": True, "live_trading_enabled": False,
                   "training_eligible": False, "strict_pit": False, "M4_complete": False},
    }
    (EVIDENCE / "validation_receipt.json").write_text(json.dumps(receipt, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"passed": receipt["passed"], "problems": problems, "pins_ok": sum(1 for v in pins.values() if v["ok"]), "pins": len(pins),
                      "rows_ok": sum(1 for v in row_checks.values() if v == "ok"), "anchors_ok": f"{receipt['anchor_checks']['ok']}/{receipt['anchor_checks']['total']}",
                      "numbers_ok": receipt["number_checks"]["ok"], "synthetic_passed": sum(1 for c in synthetic.values() if c["passed"]), "synthetic_total": len(synthetic),
                      "full_chain_passed": sum(1 for c in full_chain.values() if c.get("passed")), "full_chain_total": len(full_chain),
                      "self_check": self_check, "denials_during_validation": len(GUARD_LOG)}, ensure_ascii=False, indent=1))
    return 0 if receipt["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
