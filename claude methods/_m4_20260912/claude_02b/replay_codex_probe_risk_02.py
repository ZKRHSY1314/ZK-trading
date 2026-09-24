"""Replay of the six additional checks in codex/probe_risk_additional_02.py against the CURRENT risk-layer source.

Fixture values and expectation predicates are reproduced verbatim from Codex's probe (which itself reuses the fixture
prefix of codex/probe_risk_02.py, including the documented ``entry_phase="continuous"`` adaptation).  Codex's frozen
directory is read-only; this replay writes only claude_02b/evidence/codex_probe_risk_replay_02.json under the same
guard policy as the probe.  The receipt records, per check, whether it passed now and whether it passed in Codex's
frozen run against delivery 02 (risk layer ebd7d805...).

    backend/.venv/Scripts/python.exe -B -X utf8 "claude methods/_m4_20260912/claude_02b/replay_codex_probe_risk_02.py"
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
SOURCES = ["backend/app/research/m4_execution.py", "backend/app/research/m4_portfolio.py", "backend/app/research/m4_risk.py"]
PROBE = ROOT / "claude methods/_m4_20260912/codex/probe_risk_additional_02.py"
BASE_PROBE = ROOT / "claude methods/_m4_20260912/codex/probe_risk_02.py"
FROZEN = ROOT / "claude methods/_m4_20260912/codex/risk_review_02/additional_results.json"
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
    m = load("replay02_risk_kernel", ROOT / SOURCES[0])
    p = load("replay02_risk_ledger", ROOT / SOURCES[1])
    r = load("replay02_risk_subject", ROOT / SOURCES[2])
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

    cases = []

    def add(name, expected, passed, **actual):
        cases.append(dict(name=name, expected=expected, passed=bool(passed), actual=actual))

    # ---- verbatim from codex/probe_risk_02.py prefix (policy adaptation entry_phase="continuous" as in Codex's own probe) ----
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
        keep = ("status", "reason", "detail", "changed", "symbols", "ledger_last_executed_at", "policy_event_clock")
        out = {k: v for k, v in x.items() if k in keep}
        if "outcome" in x:
            out["outcome"] = {k: v for k, v in x["outcome"].items() if k in ("filled_quantity", "fill_price", "cash_after", "gap", "recheck", "reservation")}
        if "recheck" in x:
            out["recheck"] = x["recheck"]
        return out

    # ---- verbatim from codex/probe_risk_additional_02.py ----------------------------------------------------
    OTHER = "SYN_OTHER"

    def other_engine():
        L = ledger((p.InitialLot(OTHER, 1000, sessions[0], "1000", "syn:other-lot"),))
        E = r.PolicyEngine(kernel=m, ledger_module=p, ledger=L, policy=POL, universe=(r.UniverseMember(S, "stock", "syn_main", "syn:S"), r.UniverseMember(OTHER, "stock", "syn_main", "syn:other")),
                           benchmark_symbol="SYN_INDEX", engine_id="SYN-CODEX-OTHER")
        t = "2024-03-18T15:00:00+08:00"
        d = E.decide("D1", C, marks=(r.Mark(S, "10", t, t, "syn:S", True), r.Mark(OTHER, "1", t, t, "syn:other", True)), signals=(r.Signal("sig", S, "buy", t, t, "syn:signal", True),))
        return E, L, d["entries"][0]["intent_id"]

    old = r.Mark(OTHER, "1", "2024-03-19T09:00:00+08:00", "2024-03-19T09:00:00+08:00", "syn:other", True)
    latest = replace(old, price="20", observed_at="2024-03-19T09:45:00+08:00", available_at="2024-03-19T09:45:00+08:00")
    for name, marks in [("latest_only", (latest,)), ("old_plus_latest", (old, latest)), ("latest_plus_old", (latest, old)),
                        ("conflicting_same_time", (latest, replace(latest, price="1"))), ("conflicting_same_time_reversed", (replace(latest, price="1"), latest))]:
        E, L, iid = other_engine()
        x = E.execute(iid, C, evid(qty=1000), marks=marks)
        add(name, "No buy: latest OTHER value20000 exceeds 50% gross cap; conflicts refused",
            L.positions().get(S, 0) == 0 and (not name.startswith("conflicting") or x["status"] == "refused"), attempt=brief(x), positions=L.positions(), cash=L.snapshot()["cash"])
    E, L = eng(); d = decision(E); iid = d["entries"][0]["intent_id"]
    x1 = E.execute(iid, C, evid(time="2024-03-19T11:00:00+08:00"))
    before = E.intents(); res = E.reservations()
    ev = evid("A-earlier", "100", 1000, "2024-03-19T10:00:00+08:00"); ev = replace(ev, tradability=replace(ev.tradability, limit_up_price="200"))
    x = E.execute(iid, C, ev)
    add("backdated_attempt_cancels", "Attempt preceding applied11:00 state refused without cancel/reservation change", x["status"] == "refused" and E.intents() == before and E.reservations() == res,
        first=brief(x1), attempt=brief(x), intents_unchanged=E.intents() == before, reservations_unchanged=E.reservations() == res, reservations=E.reservations())

    frozen = json.loads(FROZEN.read_text(encoding="utf-8"))
    frozen_passed = {c["name"]: c["passed"] for c in frozen["cases"]}
    receipt = dict(schema="m4.claude_02b.codex_probe_replay.v1", observed_at_utc=datetime.now(timezone.utc).isoformat(),
                   replayed_probe=PROBE.relative_to(ROOT).as_posix(), replayed_probe_sha256=hashlib.sha256(PROBE.read_bytes()).hexdigest(),
                   base_probe=BASE_PROBE.relative_to(ROOT).as_posix(), base_probe_sha256=hashlib.sha256(BASE_PROBE.read_bytes()).hexdigest(),
                   frozen_results=FROZEN.relative_to(ROOT).as_posix(), frozen_results_sha256=hashlib.sha256(FROZEN.read_bytes()).hexdigest(),
                   frozen_source_hashes=frozen["source_hashes"], current_source_hashes=sources,
                   source_unchanged_during_replay=all(hashlib.sha256((ROOT / f).read_bytes()).hexdigest() == h for f, h in sources.items()),
                   adaptation="none beyond Codex's own entry_phase='continuous' policy (verbatim fixture prefix of codex/probe_risk_02.py); expectations unchanged",
                   cases=[{**c, "passed_on_second_delivery": frozen_passed.get(c["name"])} for c in cases],
                   summary={"checks": len(cases), "passed_now": sum(1 for c in cases if c["passed"]), "passed_on_second_delivery": sum(1 for v in frozen_passed.values() if v)},
                   guard_denials=denials, synthetic_only=True, review_only=True, live_trading_enabled=False, training_eligible=False)
    (OUT / "codex_probe_risk_replay_02.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"checks": [{"name": c["name"], "passed": c["passed"], "status": c["actual"]["attempt"]["status"]} for c in cases], "current_source_hashes": sources,
                      "summary": receipt["summary"], "guard_denials": denials}, indent=1))
    return 0 if receipt["summary"]["passed_now"] == len(cases) else 1


if __name__ == "__main__":
    sys.exit(main())
