"""R04 - audit of the 298 suspension records against their retained evidence.

For every ledger entry: verify the referenced evidence file(s) exist at the recorded
SHA-256; reconstruct the suspension interval [start, resume) on the pinned calendar and
require the ledger dates to equal exactly the calendar days of that interval inside the
symbol's contract windows; then check the boundaries against the trading store (mode=ro):
the calendar day before `start` and the `resume` day must carry price rows when they fall
inside a window, and an ongoing interval must have no price row through the window end.
Writes r04_suspension_audit.json.
"""
import hashlib
import json
import sqlite3
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

HERE = Path(__file__).resolve().parent
CM = HERE.parent
PHASE = CM / "_m2_codex_implementation_20260910"
RUN_ID = "ths_v2_20260910_041710_97ef9c09"
RUN = PHASE / "staging_runs" / RUN_ID / f"run_{RUN_ID}"
CAL = CM.parent / "backend/.venv/Lib/site-packages/akshare/file_fold/calendar.json"
LEDGER = PHASE / "pilot52_blocker_review_v3.json"
RS, RE, WS, WE, EARLY = "2023-09-04", "2026-09-04", "2022-08-24", "2023-09-01", "2022-05-01"
EXTEND = ("SZ002656", "SH600110", "SH600226")


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def ro(path):
    conn = sqlite3.connect("file:" + quote(Path(path).as_posix(), safe="/:") + "?mode=ro", uri=True)
    conn.execute("PRAGMA query_only=ON")
    return conn


def main():
    calendar = sorted({datetime.fromisoformat(str(d)).date().isoformat() for d in json.load(open(CAL, encoding="utf-8"))})
    idx = {d: i for i, d in enumerate(calendar)}
    ledger = json.load(open(LEDGER, encoding="utf-8"))["gap_ledger"]
    out = {"ledger_sha256": sha(LEDGER), "entries": len(ledger), "evidence_files": {}, "intervals": [], "problems": [], "opened": []}

    # 1. evidence files
    def check_file(rel, expected):
        p = PHASE / rel
        rec = out["evidence_files"].get(rel)
        if rec is None:
            rec = {"exists": p.is_file(), "sha256": sha(p) if p.is_file() else None, "expected": expected}
            rec["match"] = rec["sha256"] == expected
            out["evidence_files"][rel] = rec
            if not rec["match"]:
                out["problems"].append(f"evidence_file_mismatch:{rel}")
        elif rec["expected"] != expected:
            out["problems"].append(f"evidence_file_conflicting_expectation:{rel}")
        return rec

    intervals = {}
    for x in ledger:
        e = x["evidence"][0]
        if "sources" in e:
            for s in e["sources"]:
                check_file(s["path"], s["sha256"])
            key = (x["symbol"], e["start"], e.get("resume"))
            kind = "issuer_document(s)"
            files = [s["path"] for s in e["sources"]]
            through = e.get("confirmed_suspended_through")
        elif "source" in e and "observation_id" not in e:
            check_file(e["source"], e["sha256"])
            key = (x["symbol"], e["start"], e.get("resume"))
            kind = "issuer_document"
            files = [e["source"]]
            through = None
        else:
            check_file(e["source"], e["sha256"])
            key = (x["symbol"], x["date"], None)
            kind = "exchange_dom_observation"
            files = [e["source"]]
            through = x["date"]
        iv = intervals.setdefault(key, {"symbol": x["symbol"], "start": key[1], "resume": key[2], "kind": kind,
                                        "files": sorted(set(files)), "dates": [], "windows": set(), "through": through,
                                        "status": x["status"]})
        iv["dates"].append(x["date"])
        iv["windows"].add(x["window"])
        if x["frozen_gate_exemption"] is not False:
            out["problems"].append(f"frozen_gate_exemption_not_false:{x['symbol']}:{x['date']}")

    # 2. interval reconstruction on the calendar + 3. boundary checks against the store
    conn = ro(RUN / "trading.sqlite3"); out["opened"].append(str(RUN / "trading.sqlite3"))
    try:
        prices = defaultdict(set)
        for s, d in conn.execute("SELECT symbol, trade_date FROM daily_bar_cache"):
            prices[s].add(d)
    finally:
        conn.close()
    # window membership per symbol (mirrors the contract: research + original warmup, or extended warmup)
    def in_window(sym, d):
        if RS <= d <= RE:
            return True
        lo = EARLY if sym in EXTEND else WS
        return lo <= d <= WE

    for key, iv in sorted(intervals.items(), key=lambda kv: (kv[0][0], kv[0][1])):
        sym, start, resume = key
        dates = sorted(iv["dates"])
        rec = {"symbol": sym, "start": start, "resume": resume, "kind": iv["kind"], "status": iv["status"],
               "files": iv["files"], "ledger_dates": len(dates), "first": dates[0], "last": dates[-1],
               "windows": sorted(iv["windows"]), "confirmed_suspended_through": iv["through"], "checks": {}}
        if iv["kind"] == "exchange_dom_observation":
            expected = [start]
        else:
            if start not in idx:
                out["problems"].append(f"start_not_calendar:{sym}:{start}"); rec["checks"]["start_on_calendar"] = False
            if resume is not None and resume not in idx:
                out["problems"].append(f"resume_not_calendar:{sym}:{resume}"); rec["checks"]["resume_on_calendar"] = False
            hi = idx[resume] if resume in idx else len(calendar)
            expected = [d for d in calendar[idx.get(start, 0):hi] if in_window(sym, d)] if start in idx else []
        rec["checks"]["ledger_dates_equal_interval_calendar_days"] = dates == expected
        if dates != expected:
            rec["only_ledger"] = sorted(set(dates) - set(expected))[:10]
            rec["only_interval"] = sorted(set(expected) - set(dates))[:10]
            out["problems"].append(f"interval_mismatch:{sym}:{start}")
        # boundaries
        p = prices.get(sym, set())
        if start in idx:
            # walk back over any contiguous ledger suspension dates (adjacent intervals) to the
            # last calendar day that is NOT itself a suspension, then require a price row there
            all_susp = {d for k, v in intervals.items() if k[0] == sym for d in v["dates"]}
            j = idx[start] - 1
            while j >= 0 and calendar[j] in all_susp:
                j -= 1
            prev = calendar[j] if j >= 0 else None
            if prev and in_window(sym, prev):
                rec["checks"]["price_row_on_last_trading_day_before_interval"] = prev in p
                rec["last_trading_day_before_interval"] = prev
                if prev not in p:
                    out["problems"].append(f"no_price_before_start:{sym}:{prev}")
        if resume is not None:
            if in_window(sym, resume):
                rec["checks"]["price_row_on_resume_day"] = resume in p
                if resume not in p:
                    out["problems"].append(f"no_price_on_resume:{sym}:{resume}")
        else:
            if iv["kind"] != "exchange_dom_observation":
                tail = [d for d in calendar[idx[start]:] if d <= RE]
                rec["checks"]["ongoing_no_price_through_window_end"] = not any(d in p for d in tail)
                rec["ongoing_window_end"] = RE
                if any(d in p for d in tail):
                    out["problems"].append(f"ongoing_has_price:{sym}")
        rec["checks"]["no_price_row_inside_interval"] = not any(d in p for d in dates)
        if any(d in p for d in dates):
            out["problems"].append(f"price_inside_suspension:{sym}:{start}")
        if iv["through"] and iv["kind"] != "exchange_dom_observation":
            rec["checks"]["confirmed_through_covers_last"] = iv["through"] >= dates[-1]
        out["intervals"].append(rec)

    out["summary"] = {"intervals": len(out["intervals"]),
                      "ongoing": [i["symbol"] + " from " + i["start"] for i in out["intervals"] if i["resume"] is None and i["kind"] != "exchange_dom_observation"],
                      "exchange_dom_only": [i["symbol"] + " " + i["start"] for i in out["intervals"] if i["kind"] == "exchange_dom_observation"],
                      "evidence_files": len(out["evidence_files"]),
                      "evidence_files_ok": sum(1 for r in out["evidence_files"].values() if r["match"]),
                      "problems": len(out["problems"])}
    json.dump(out, open(HERE / "r04_suspension_audit.json", "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    print(json.dumps(out["summary"], ensure_ascii=False, indent=1))
    for i in out["intervals"]:
        flags = {k: v for k, v in i["checks"].items() if v is False}
        print(f"{i['symbol']} {i['start']} -> {i['resume']} [{i['kind']}] n={i['ledger_dates']} files={len(i['files'])} {('FAILED ' + str(flags)) if flags else 'ok'}")
    print("problems:", out["problems"])
    return 0 if not out["problems"] else 1


if __name__ == "__main__":
    sys.exit(main())
