"""Replay of the five checks in codex/probe_risk_01.py against the CURRENT risk-layer source (delivery 02).

Fixture values and expectation predicates are reproduced verbatim from Codex's probe.  Documented adaptation: the
corrected contract binds an intent's execution phase at creation (policy.entry_phase / exit_phase); Codex's fixture
executes continuous attempts at 10:00, so the RiskPolicy is built with ``entry_phase="continuous"`` (all other
positional parameters unchanged).  Codex's frozen directory is read-only; this replay writes only
claude_02b/evidence/codex_probe_risk_replay_01.json under the same guard policy as the probe.

    backend/.venv/Scripts/python.exe -B -X utf8 "claude methods/_m4_20260912/claude_02b/replay_codex_probe_risk_01.py"
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from dataclasses import replace
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
OUT = HERE / "evidence"
SOURCES = ["backend/app/research/m4_execution.py", "backend/app/research/m4_portfolio.py", "backend/app/research/m4_risk.py"]
PROBE = ROOT / "claude methods/_m4_20260912/codex/probe_risk_01.py"
FROZEN = ROOT / "claude methods/_m4_20260912/codex/risk_review_01/results.json"
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
    sources = {rel: hashlib.sha256((ROOT / rel).read_bytes()).hexdigest() for rel in SOURCES}
    sys.addaudithook(guard)
    m = load("replay_risk_kernel", ROOT / SOURCES[0])
    p = load("replay_risk_ledger", ROOT / SOURCES[1])
    r = load("replay_risk_subject", ROOT / SOURCES[2])
    # ---- Codex synthetic kernel fixture (verbatim values from codex/probe_m4_working_01.py) --------------
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

    def snap(L):
        return json.loads(json.dumps(L.snapshot()))

    cases = []

    def add(name, expected, passed, **actual):
        cases.append(dict(name=name, expected=expected, passed=bool(passed), actual=actual))

    # ---- verbatim from codex/probe_risk_01.py (policy adapted: entry_phase="continuous", see module docstring) ----
    POL = r.RiskPolicy("SYN-CODEX-P", "hypothetical_fixture", "0.5", "0.5", "0", "0.05", None, 5, 2, 0, "0.5", 1, ("stop_loss", "max_holding"), entry_phase="continuous")
    C = r.DecisionContext(sessions[0], "2024-03-18T16:00:00+08:00", req.calendar, req.fee_schedule, req.assumptions)

    def eng():
        L = ledger()
        E = r.PolicyEngine(kernel=m, ledger_module=p, ledger=L, policy=POL, universe=(r.UniverseMember(S, "stock", "syn_main", "syn:listing"),), benchmark_symbol="SYN_INDEX", engine_id="SYN-CODEX-RISK")
        return E, L

    def decision(E, did="D1", c=C):
        t = c.decision_session + "T15:00:00+08:00"
        return E.decide(did, c, marks=(r.Mark(S, "10.00", t, t, "syn:mark", True),), signals=(r.Signal(did + "-sig", S, "buy", t, t, "syn:signal", True),))

    def evid(aid="A1", price="10", qty=100, time="2024-03-19T10:00:00+08:00"):
        return r.AttemptEvidence(aid, time, sessions[1], "continuous", replace(req.tradability, limit_up_price="50", limit_down_price="1"),
                                 replace(req.price, price=price, field="last_trade", observed_at=time, available_at=time),
                                 replace(req.capacity, capacity_id=aid, quantity=qty, basis="available_at_attempt", observed_at=time, available_at=time))

    def brief(x):
        return {k: v for k, v in x.items() if k in ("status", "reason", "detail", "changed")} | ({"outcome": {k: v for k, v in x["outcome"].items() if k in ("filled_quantity", "fill_price", "cash_after", "gap", "recheck", "reservation")}} if "outcome" in x else {})

    E, L = eng(); d = decision(E); iid = d["entries"][0]["intent_id"]; x = E.execute(iid, C, evid(qty=1000)); s = L.snapshot()
    add("positive_sized_entry", "400shares, cash5994.96", s["positions"].get(S) == 400 and s["cash"] == "5994.96", attempt=brief(x), cash=s["cash"], positions=s["positions"])
    # Partial fills must debit the SAME reserved budget, not reuse all 5000 for the remainder.
    E, L = eng(); d = decision(E); iid = d["entries"][0]["intent_id"]; x1 = E.execute(iid, C, evid()); x2 = E.execute(iid, C, evid("A2", "14", 1000, "2024-03-19T11:00:00+08:00")); s = L.snapshot()
    spent = Decimal("10000") - Decimal(s["cash"])
    add("cumulative_intent_budget", "All partial fills total cost <= original reserved5000", spent <= Decimal("5000"), spent=str(spent), first=brief(x1), second=brief(x2), positions=s["positions"], reservations=E.reservations())
    # Unavailable/mismatched execution evidence cannot cancel and release a valid intent before kernel validation.
    E, L = eng(); d = decision(E); iid = d["entries"][0]["intent_id"]; before = E.intents(); ev = evid(price="100")
    ev = replace(ev, price=replace(ev.price, observed_at="2024-03-20T10:00:00+08:00", available_at="2024-03-20T10:00:00+08:00"))
    x = E.execute(iid, C, ev)
    add("future_price_cancels_intent", "Future execution price rejected before any intent/reservation change", E.intents() == before and E.reservations()["reserved_cash"] == "5000.00",
        attempt=brief(x), reservations=E.reservations(), intents_unchanged=E.intents() == before)
    # First fill must preserve decision-time calendar expiry too, not bind only on first ledger execution.
    E, L = eng(); d = decision(E); iid = d["entries"][0]["intent_id"]; changed = replace(C, calendar=replace(C.calendar, close_time="16:00"))
    x = E.execute(iid, changed, evid(time="2024-03-19T15:30:00+08:00"))
    add("decision_calendar_rewritten_before_first_fill", "Intent expires original15:00; changed execution context must not fill15:30", not L.positions(), attempt=brief(x), positions=L.positions())
    # Current ledger state must not leak backward into decisions older than an applied execution.
    E, L = eng(); d = decision(E); iid = d["entries"][0]["intent_id"]; x = E.execute(iid, C, evid()); back = decision(E, "D-back")
    add("decision_before_last_fill", "Backdated decision after a fill refused instead of consuming future holdings", back.get("status") == "refused",
        decision_status=back.get("status"), refusals=back.get("refusals"), positions=L.positions())

    frozen = json.loads(FROZEN.read_text(encoding="utf-8"))
    frozen_passed = {c["name"]: c["passed"] for c in frozen["cases"]}
    receipt = dict(schema="m4.claude_02b.codex_probe_replay.v1", observed_at_utc=datetime.now(timezone.utc).isoformat(),
                   replayed_probe=PROBE.relative_to(ROOT).as_posix(), replayed_probe_sha256=hashlib.sha256(PROBE.read_bytes()).hexdigest(),
                   frozen_results=FROZEN.relative_to(ROOT).as_posix(), frozen_results_sha256=hashlib.sha256(FROZEN.read_bytes()).hexdigest(),
                   frozen_source_hashes=frozen["source_hashes"], current_source_hashes=sources,
                   source_unchanged_during_replay=all(hashlib.sha256((ROOT / f).read_bytes()).hexdigest() == h for f, h in sources.items()),
                   adaptation="RiskPolicy(..., entry_phase='continuous'): the corrected contract binds the execution phase at intent creation; Codex's attempts are continuous at 10:00; expectations unchanged",
                   cases=[{**c, "passed_on_first_delivery": frozen_passed.get(c["name"])} for c in cases],
                   summary={"checks": len(cases), "passed_now": sum(1 for c in cases if c["passed"]), "passed_on_first_delivery": sum(1 for v in frozen_passed.values() if v)},
                   guard_denials=denials, synthetic_only=True, review_only=True, live_trading_enabled=False, training_eligible=False)
    (OUT / "codex_probe_risk_replay_01.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"checks": [{"name": c["name"], "passed": c["passed"]} for c in cases], "current_source_hashes": sources, "summary": receipt["summary"], "guard_denials": denials}, indent=1))
    return 0 if receipt["summary"]["passed_now"] == len(cases) else 1


if __name__ == "__main__":
    sys.exit(main())
