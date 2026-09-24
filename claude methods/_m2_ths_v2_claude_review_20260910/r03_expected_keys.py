"""R03 - independent expected-key derivation and store partition audit.

Derives, WITHOUT importing any phase module, the set of trading-day keys each of the 52
securities must carry from (calendar ∩ listing window), removes the reviewed suspension
dates, applies the three-stock warmup extension rule exactly as the approved contract
states it (last 250 eligible sessions in 2022-05-01..2023-09-01), and compares the result
against BOTH candidate stores' coverage_inventory and price tables (mode=ro, query_only).

Inputs read: pinned calendar.json, pinned pilot_symbols.csv, pilot52_blocker_review_v3.json
(gap_ledger), qualification_v2_reviewed.json (for comparison only, never as a source of
expected keys). Writes r03_expected_keys.json.
"""
import csv
import hashlib
import json
import sqlite3
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

HERE = Path(__file__).resolve().parent
CM = HERE.parent
PHASE = CM / "_m2_codex_implementation_20260910"
RUN_ID = "ths_v2_20260910_041710_97ef9c09"
RUN = PHASE / "staging_runs" / RUN_ID / f"run_{RUN_ID}"
CAL = CM.parent / "backend/.venv/Lib/site-packages/akshare/file_fold/calendar.json"
MANIFEST = CM / "_m1_closure/pilot_symbols.csv"
LEDGER = PHASE / "pilot52_blocker_review_v3.json"
QUAL = PHASE / "qualification_v2_reviewed.json"
PINS = {CAL: "f1f1ce33c5cceb5c530c3271fc951405cb5624d2f30becec85dc7a85fd47e656",
        MANIFEST: "97e251ae84fc927486127a96b4966ed8fc59fac0b744b7d6f186b2b1548886fe",
        LEDGER: "58214acbb4148d95ab572d1d0ecfd6833817bb5ce5c49a3572cf598ba24138a8",
        QUAL: "992bd79ce9d2e38d1a0a8ae2f9890cd26daebcd3d2ab664d5caab171ec3e0f37"}
RS, RE = "2023-09-04", "2026-09-04"
WS, WE = "2022-08-24", "2023-09-01"
EARLY = "2022-05-01"
EXTEND = ("SZ002656", "SH600110", "SH600226")
FROZEN_SHORT = {"BJ920001": 167, "BJ920006": 75, "BJ920002": 0, "BJ920003": 0, "BJ920005": 0,
                "BJ920007": 0, "BJ920519": 0, "BJ920627": 0, "SH603075": 0, "SH688549": 0,
                "SH688702": 0, "SZ301251": 0, "SZ301507": 0, "SZ301529": 0}


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def ro(path):
    conn = sqlite3.connect("file:" + quote(Path(path).as_posix(), safe="/:") + "?mode=ro", uri=True)
    conn.execute("PRAGMA query_only=ON")
    return conn


def main():
    out = {"pins": {}, "problems": [], "per_symbol": {}, "opened": []}
    for p, expected in PINS.items():
        actual = sha(p)
        out["pins"][str(p)] = {"sha256": actual, "match": actual == expected}
        if actual != expected:
            out["problems"].append(f"pin_mismatch:{p.name}")
    calendar = sorted({datetime.fromisoformat(str(d)).date().isoformat() for d in json.load(open(CAL, encoding="utf-8"))})
    with open(MANIFEST, encoding="utf-8-sig") as fh:
        entries = {r["symbol"]: r for r in csv.DictReader(fh)}
    if len(entries) != 52:
        out["problems"].append(f"manifest_count:{len(entries)}")
    ledger = json.load(open(LEDGER, encoding="utf-8"))["gap_ledger"]
    susp = defaultdict(set)
    for g in ledger:
        susp[g["symbol"]].add(g["date"])
    if sum(len(v) for v in susp.values()) != 298 or len(ledger) != 298:
        out["problems"].append("ledger_count_not_298")
    cal_set = set(calendar)

    expected_price, expected_susp, expected_all = {}, {}, {}
    for sym, e in entries.items():
        ld, dd = e.get("list_date") or None, e.get("delist_date") or None
        listed = lambda d: (not ld or d >= ld) and (not dd or d <= dd)
        research = [d for d in calendar if RS <= d <= RE and listed(d)]
        warm_orig = [d for d in calendar if WS <= d <= WE and listed(d)]
        s = susp.get(sym, set())
        # suspensions must be calendar days inside the listed window
        bad = [d for d in s if d not in cal_set or not listed(d)]
        if bad:
            out["problems"].append(f"suspension_not_calendar_or_unlisted:{sym}:{bad[:5]}")
        s_res = {d for d in s if RS <= d <= RE}
        s_warm_orig = {d for d in s if WS <= d <= WE}
        if sym in EXTEND:
            early = [d for d in calendar if EARLY <= d <= WE and listed(d)]
            early_halts = {d for d in s if d <= WE}
            eligible = sorted(set(early) - early_halts)
            selected = set(eligible[-250:])
            warm_price = selected
            # every original-window price date must survive the extension
            if not ({d for d in warm_orig if d not in s} <= selected):
                out["problems"].append(f"extension_drops_original_warmup:{sym}")
            warm_all = set(warm_orig) | selected | {d for d in early_halts if d >= min(selected)}
            warm_susp = {d for d in s if d <= WE and (d in warm_orig or d >= min(selected))}
        else:
            warm_price = set(warm_orig) - s_warm_orig
            warm_susp = s_warm_orig
            warm_all = set(warm_orig)
        res_price = set(research) - s_res
        expected_price[sym] = sorted(res_price | warm_price)
        expected_susp[sym] = sorted(s_res | warm_susp)
        expected_all[sym] = sorted(set(expected_price[sym]) | set(expected_susp[sym]))
        out["per_symbol"][sym] = {"stratum": e["stratum"], "list_date": ld,
                                  "research_keys": len(research), "research_susp": len(s_res), "research_price": len(res_price),
                                  "warmup_price": len(warm_price), "warmup_susp": len(warm_susp),
                                  "all_susp_in_ledger": len(s), "extended": sym in EXTEND}
    tot = {"research_price": sum(v["research_price"] for v in out["per_symbol"].values()),
           "research_keys": sum(v["research_keys"] for v in out["per_symbol"].values()),
           "research_susp": sum(v["research_susp"] for v in out["per_symbol"].values()),
           "warmup_price": sum(v["warmup_price"] for v in out["per_symbol"].values()),
           "warmup_susp": sum(v["warmup_susp"] for v in out["per_symbol"].values()),
           "price_total": sum(len(v) for v in expected_price.values()),
           "susp_total": sum(len(v) for v in expected_susp.values())}
    out["derived_totals"] = tot
    # unaccounted ledger dates (a suspension date outside every window)
    accounted = sum(len(v) for v in expected_susp.values())
    if accounted != 298:
        out["problems"].append(f"ledger_dates_not_all_inside_windows:{accounted}")
    shorts = {s: v["warmup_price"] for s, v in out["per_symbol"].items() if v["stratum"] != "benchmark" and v["warmup_price"] < 250}
    out["derived_warmup_shortfalls"] = shorts
    out["shortfalls_match_frozen"] = shorts == FROZEN_SHORT

    # compare against the reviewed qualification bundle (comparison only)
    qual = json.load(open(QUAL, encoding="utf-8"))
    qmatch = {"expected_price_dates_equal": 0, "suspended_dates_equal": 0, "mismatch": []}
    for scope in qual["scopes"]:
        sym = scope["symbol"]
        if scope["expected_price_dates"] == expected_price[sym]:
            qmatch["expected_price_dates_equal"] += 1
        else:
            qmatch["mismatch"].append((sym, "price"))
        if sorted(scope["suspended_dates"]) == sorted(susp.get(sym, ())):
            qmatch["suspended_dates_equal"] += 1
        else:
            qmatch["mismatch"].append((sym, "susp"))
    out["bundle_comparison"] = qmatch

    # compare against both stores
    for role, path, table in (("trading", RUN / "trading.sqlite3", "daily_bar_cache"), ("history", RUN / "history.sqlite3", "daily_bars")):
        conn = ro(path); out["opened"].append(str(path))
        try:
            inv = defaultdict(dict)
            for s, d, c in conn.execute("SELECT symbol,trade_date,classification FROM coverage_inventory"):
                inv[s][d] = c
            prices = defaultdict(set)
            for s, d in conn.execute(f"SELECT symbol,trade_date FROM {table}"):
                prices[s].add(d)
            srec = defaultdict(set)
            for s, d in conn.execute("SELECT symbol,trade_date FROM suspension_records"):
                srec[s].add(d)
            store = {"symbols_in_prices": len(prices), "price_rows": sum(len(v) for v in prices.values()),
                     "suspension_rows": sum(len(v) for v in srec.values()), "inventory_keys": sum(len(v) for v in inv.values()),
                     "mismatches": []}
            for sym in entries:
                ep, es = set(expected_price[sym]), set(expected_susp[sym])
                ap, asp = prices.get(sym, set()), srec.get(sym, set())
                inv_p = {d for d, c in inv[sym].items() if c == "price"}
                inv_s = {d for d, c in inv[sym].items() if c == "full_day_suspension"}
                for name, a, b in (("price_vs_derived", ap, ep), ("susp_vs_derived", asp, es),
                                   ("inventory_price_vs_table", inv_p, ap), ("inventory_susp_vs_table", inv_s, asp)):
                    if a != b:
                        store["mismatches"].append({"symbol": sym, "check": name, "only_store": sorted(a - b)[:10], "only_derived": sorted(b - a)[:10],
                                                    "n_store": len(a), "n_derived": len(b)})
                if ap & asp:
                    store["mismatches"].append({"symbol": sym, "check": "price_suspension_overlap", "dates": sorted(ap & asp)[:10]})
            store["research_view"] = conn.execute("SELECT COUNT(*) FROM research_prices").fetchone()[0]
            store["warmup_view"] = conn.execute("SELECT COUNT(*) FROM warmup_prices").fetchone()[0]
            store["warmup_per_stock_lt250"] = dict(conn.execute(
                f"SELECT symbol, COUNT(*) FROM warmup_prices GROUP BY symbol HAVING COUNT(*) < 250").fetchall())
            # any date outside calendar or research/warmup windows?
            allp = {(s, d) for s, ds in prices.items() for d in ds}
            store["price_dates_off_calendar"] = sorted(d for s, d in allp if d not in cal_set)[:10]
            store["price_dates_between_windows"] = sorted({d for s, d in allp if WE < d < RS})[:10]
            store["price_dates_before_early"] = sorted({d for s, d in allp if d < EARLY})[:10]
            store["error_pseudo_dates"] = conn.execute(f"SELECT COUNT(*) FROM {table} WHERE trade_date NOT GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'").fetchone()[0]
            store["duplicate_business_keys"] = conn.execute(f"SELECT COUNT(*) FROM (SELECT symbol,trade_date,COUNT(*) c FROM {table} GROUP BY 1,2 HAVING c>1)").fetchone()[0]
            out[f"store_{role}"] = store
        finally:
            conn.close()
    json.dump(out, open(HERE / "r03_expected_keys.json", "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    print("pins:", {Path(k).name: v["match"] for k, v in out["pins"].items()})
    print("derived totals:", tot)
    print("derived shortfalls == frozen 14:", out["shortfalls_match_frozen"], shorts)
    print("bundle comparison:", qmatch)
    for role in ("trading", "history"):
        s = out[f"store_{role}"]
        print(f"{role}: prices={s['price_rows']} susp={s['suspension_rows']} inv={s['inventory_keys']} research_view={s['research_view']} warmup_view={s['warmup_view']} "
              f"mismatches={len(s['mismatches'])} off_cal={s['price_dates_off_calendar']} between={s['price_dates_between_windows']} before_early={s['price_dates_before_early']} "
              f"error_dates={s['error_pseudo_dates']} dup_keys={s['duplicate_business_keys']}")
        for m in s["mismatches"][:20]:
            print("   MISMATCH", m)
        print("   warmup<250:", s["warmup_per_stock_lt250"])
    print("problems:", out["problems"])
    return 0 if not out["problems"] and all(not out[f"store_{r}"]["mismatches"] for r in ("trading", "history")) else 1


if __name__ == "__main__":
    sys.exit(main())
