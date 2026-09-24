"""Replay of the five checks in codex/probe_portfolio_01.py against the CURRENT ledger source (delivery 02).

Fixture values and expectation predicates are reproduced verbatim from Codex's probe; the only adaptation is the
corrected ledger API ``account_state(as_of, symbol)`` (delivery 01 pooled every symbol into one symbol-less
inventory, which was finding P1-1).  Codex's frozen directory is read-only; this replay writes only
claude_02a/evidence/codex_probe_portfolio_replay_01.json under the same guard policy as the probe.

    backend/.venv/Scripts/python.exe -B -X utf8 "claude methods/_m4_20260912/claude_02a/replay_codex_probe_portfolio_01.py"
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
OUT = HERE / "evidence"
KERNEL = ROOT / "backend/app/research/m4_execution.py"
LEDGER = ROOT / "backend/app/research/m4_portfolio.py"
PROBE = ROOT / "claude methods/_m4_20260912/codex/probe_portfolio_01.py"
FROZEN = ROOT / "claude methods/_m4_20260912/codex/portfolio_review_01/results.json"
denials: list[str] = []


def guard(event, args):
    deny = event.startswith(("sqlite3.", "socket.", "subprocess.")) or event in {"os.system", "os.exec", "os.posix_spawn", "os.remove", "os.rename", "os.rmdir", "os.mkdir"}
    if event == "open":
        path, mode, flags = args
        if (isinstance(mode, str) and any(c in mode for c in "wax+")) or (isinstance(flags, int) and flags & (1 | 2 | 64 | 512 | 1024)):
            deny = not isinstance(path, (str, bytes)) or not Path(path).resolve().is_relative_to(HERE.resolve())
    if deny:
        denials.append(event)
        raise RuntimeError("Guard denied " + event)


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    obj = importlib.util.module_from_spec(spec)
    sys.modules[name] = obj
    spec.loader.exec_module(obj)
    return obj


def main() -> int:
    sources = {"backend/app/research/m4_execution.py": hashlib.sha256(KERNEL.read_bytes()).hexdigest(), "backend/app/research/m4_portfolio.py": hashlib.sha256(LEDGER.read_bytes()).hexdigest()}
    sys.addaudithook(guard)
    m = load("replay_portfolio_kernel", KERNEL)
    p = load("replay_portfolio_subject", LEDGER)
    # ---- Codex synthetic kernel fixture (verbatim values from codex/probe_m4_working_01.py) -------------
    S = "SYN_CODEX_01"
    T = "2024-03-19T09:30:00+08:00"
    sessions = ("2024-03-18", "2024-03-19", "2024-03-20", "2024-03-21")
    req = m.ExecutionRequest(
        decision=m.Decision("D", "SYN_CODEX_01", "buy", sessions[0], "2024-03-18T16:00:00+08:00", (m.InputAvailability("prior_close", "2024-03-18T15:05:00+08:00", "syn:prior_close"),), "syn:rule"),
        order=m.Order("O", "D", S, "buy", 100, "10.00", "2024-03-19T09:00:00+08:00", T, 1, "open_auction"),
        instrument=m.Instrument(S, "stock", "syn_main", "syn:listing", "syn:calendar", True),
        calendar=m.SessionCalendar(sessions, "+08:00", "09:30", "15:00", "syn:calendar", "2024-01-01T00:00:00+08:00", True),
        tradability=m.TradabilityEvidence(S, sessions[1], "tradable", "none", "band", "11.00", "9.00", "not_st", "seasoned", T, T, "syn:tradable", True),
        price=m.PriceObservation(S, "10.00", "open_auction_print", T, T, "syn:price", "contemporaneous", True),
        capacity=m.LiquidityCapacity(S, "C", 1000, "share", "auction_matched_quantity", T, T, "syn:capacity", "contemporaneous", True),
        account=m.AccountState("SYN_CODEX_ACCOUNT", "10000.00", (), "2024-03-19T09:00:00+08:00", True),
        fee_schedule=m.FeeSchedule("HYPOTHETICAL_CODEX", "1", "hypothetical_fixture", "syn:fees", "2024-01-01", None, ("syn_main",), "0.0003", "0.0003", "5.00", "0.00001", "0.0005"),
        assumptions=m.ExecutionAssumptions("HYPOTHETICAL_CODEX", "hypothetical_fixture", "syn:policy", "0", "1", "0.01", m.LotPolicy("syn:lot", 100, 100, 100, "whole_odd_remainder_only", 1000000), m.SettlementPolicy("syn:T+1", 1)),
        attempt=m.ExecutionAttempt("A", T, sessions[1], "open_auction"),
    )

    def ledger(lots=()):
        return p.PortfolioLedger(m, ledger_id="SYN-CODEX-L", account_ref="SYN_CODEX_ACCOUNT", initial_cash="10000.00", initial_lots=lots)

    def event(L, seq, r):   # adaptation: the corrected ledger derives account state per symbol
        return p.AttemptEvent("E" + str(seq), seq, replace(r, account=L.account_state(r.attempt.executed_at, r.order.symbol)))

    def snap(L):
        return json.loads(json.dumps(L.snapshot()))

    def economic(s):
        return {k: v for k, v in s.items() if k != "records"}

    cases = []

    def add(name, expected, passed, **actual):
        cases.append(dict(name=name, expected=expected, passed=bool(passed), actual=actual))

    # 1: Normal round-trip positive control.
    L = ledger(); L.apply(event(L, 1, req))
    T2 = "2024-03-20T09:30:00+08:00"
    sell = replace(req, decision=replace(req.decision, decision_id="D-S", side="sell", decision_session=sessions[1], decided_at="2024-03-19T16:00:00+08:00"),
                   order=replace(req.order, order_id="O-S", decision_id="D-S", side="sell", limit_price="11.00", submitted_at="2024-03-20T09:00:00+08:00", eligible_from=T2),
                   price=replace(req.price, price="11.00", observed_at=T2, available_at=T2), tradability=replace(req.tradability, session=sessions[2], observed_at=T2, available_at=T2),
                   capacity=replace(req.capacity, capacity_id="C-S", observed_at=T2, available_at=T2), attempt=replace(req.attempt, attempt_id="A-S", session=sessions[2], executed_at=T2))
    r = L.apply(event(L, 2, sell)); s = L.snapshot()
    add("positive_round_trip", "Cash10089.43, PnL89.43, no position", s["cash"] == "10089.43" and s["realized_pnl_total"] == "89.43" and not s["positions"],
        record_status=r["status"], cash=s["cash"], realized=s["realized_pnl_total"], reconcile_ok=L.reconcile()["ok"])
    # 2: Another symbol's settled shares cannot legalize same-session target shares.
    lots = (p.InitialLot(S, 100, sessions[1], "1000.00", "syn:today-target"), p.InitialLot("SYN_OTHER", 100, sessions[0], "1000.00", "syn:old-other"))
    L = ledger(lots); ss = replace(req, decision=replace(req.decision, side="sell"), order=replace(req.order, side="sell"))
    before = snap(L); r = L.apply(event(L, 1, ss)); after = snap(L)
    add("cross_symbol_t1", "Target same-session shares remain unsold despite other settled symbol",
        r["status"] != "applied" and after["positions"].get(S) == 100 and after["cash"] == before["cash"],
        record_status=r["status"], reasons=r["reasons"], positions_after=after["positions"], cash_after=after["cash"])
    # 3: No target shares; kernel's wrongly pooled inventory must not cause partial commits.
    L = ledger((p.InitialLot("SYN_OTHER", 100, sessions[0], "1000.00", "syn:old-other"),))
    before = snap(L); e = event(L, 1, ss); r = L.apply(e); after = snap(L); replay = L.apply(e)
    add("rejection_atomicity", "Rejected sale preserves all execution state and does not consume id/capacity",
        r["status"] != "applied" and economic(before) == economic(after) and replay["status"] != "skipped_duplicate",
        record_status=r["status"], committed=r["committed"], economic_unchanged=economic(before) == economic(after), replay_status=replay["status"], state_hash_after=after["state_hash"], state_hash_before=before["state_hash"])
    # 4: Returned views must not alias internal audit/provenance state.
    L = ledger(); r = L.apply(event(L, 1, req)); before = snap(L)
    r["state_after"]["cash"] = "999999.00"
    snapview = L.snapshot(); snapview["capacity"]["C"]["evidence"]["source_ref"] = "syn:mutated-via-view"
    after = snap(L)
    add("detached_read_views", "Mutating returned record/snapshot cannot change stored history/evidence",
        L.records[0]["state_after"]["cash"] != "999999.00" and economic(before) == economic(after),
        record_history_cash=L.records[0]["state_after"]["cash"], evidence_source_ref_after=after["capacity"]["C"]["evidence"]["source_ref"])
    # 5: Same order id cannot silently move its original expiry through a new attempt.
    L = ledger(); T10 = "2024-03-19T10:00:00+08:00"
    cont = replace(req, order=replace(req.order, quantity=200, execution_phase="continuous"), attempt=replace(req.attempt, executed_at=T10, phase="continuous"),
                   price=replace(req.price, observed_at=T10, available_at=T10), capacity=replace(req.capacity, quantity=100, observed_at=T10, available_at=T10))
    first = L.apply(event(L, 1, cont)); Tnext = "2024-03-20T10:00:00+08:00"
    later = replace(cont, decision=replace(cont.decision, decision_session=sessions[1], decided_at="2024-03-19T16:00:00+08:00"),
                    order=replace(cont.order, quantity=100, submitted_at="2024-03-20T09:00:00+08:00", eligible_from="2024-03-20T09:30:00+08:00"),
                    attempt=replace(cont.attempt, attempt_id="A-later", session=sessions[2], executed_at=Tnext), price=replace(cont.price, observed_at=Tnext, available_at=Tnext),
                    capacity=replace(cont.capacity, capacity_id="C-later", observed_at=Tnext, available_at=Tnext), tradability=replace(cont.tradability, session=sessions[2], observed_at=T2, available_at=T2))
    r = L.apply(event(L, 2, later))
    add("same_order_rewrites_expiry", "Expired original order must not refill by replacing decision/eligible terms", first["status"] == "applied" and r["status"] != "applied",
        first_status=first["status"], later_status=r["status"], later_reasons=r["reasons"], positions=L.snapshot()["positions"])

    frozen = json.loads(FROZEN.read_text(encoding="utf-8"))
    frozen_passed = {c["name"]: c["passed"] for c in frozen["cases"]}
    receipt = dict(schema="m4.claude_02a.codex_probe_replay.v1", observed_at_utc=datetime.now(timezone.utc).isoformat(),
                   replayed_probe=PROBE.relative_to(ROOT).as_posix(), replayed_probe_sha256=hashlib.sha256(PROBE.read_bytes()).hexdigest(),
                   frozen_results=FROZEN.relative_to(ROOT).as_posix(), frozen_results_sha256=hashlib.sha256(FROZEN.read_bytes()).hexdigest(),
                   frozen_source_hashes=frozen["source_hashes"], current_source_hashes=sources,
                   source_unchanged_during_replay=all(hashlib.sha256((ROOT / f).read_bytes()).hexdigest() == h for f, h in sources.items()),
                   adaptation="account_state(as_of, symbol): the corrected ledger derives inventory per symbol; expectations unchanged",
                   cases=[{**c, "passed_on_first_delivery": frozen_passed.get(c["name"])} for c in cases],
                   summary={"checks": len(cases), "passed_now": sum(1 for c in cases if c["passed"]), "passed_on_first_delivery": sum(1 for v in frozen_passed.values() if v)},
                   guard_denials=denials, synthetic_only=True, review_only=True, live_trading_enabled=False, training_eligible=False)
    (OUT / "codex_probe_portfolio_replay_01.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"checks": [{"name": c["name"], "passed": c["passed"]} for c in cases], "current_source_hashes": sources, "summary": receipt["summary"], "guard_denials": denials}, indent=1))
    return 0 if receipt["summary"]["passed_now"] == len(cases) else 1


if __name__ == "__main__":
    sys.exit(main())
