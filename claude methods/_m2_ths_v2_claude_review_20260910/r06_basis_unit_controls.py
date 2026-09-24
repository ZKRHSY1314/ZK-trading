"""R06 - independent replay of the unadjusted-basis controls, the native-interface depth
claim, the unit anchors and the BJ920006 block-scope arithmetic.

(a) Parses the six retained control bodies (SH600011 / BJ920000 x adjustment 0/1/2) with
    the pinned pure parser and re-derives, with my own code, the cash-forward relation
    P0 - P1 == sum(official cash after day) on every OHLC, volume/amount invariance across
    modes, and that modes 1 and 2 are each distinct from mode 0. Cash events and their
    official-document hashes are re-verified on disk.
(b) Ties the mode-0 control series to the staged corpus rows for the two control symbols.
(c) Checks the "native interface > 500 rows" claim from the captures themselves.
(d) Re-verifies the official unit anchors against the parsed rows.
(e) Recomputes the BJ920006 / 2023-12-04 block-scope arithmetic with Decimal and checks
    the residual against BOTH the 2% envelope and the strict auction [low, high].
Writes r06_basis_unit_controls.json.
"""
import hashlib
import importlib.util
import json
import sqlite3
import sys
from decimal import Decimal
from pathlib import Path
from urllib.parse import quote

HERE = Path(__file__).resolve().parent
CM = HERE.parent
PROJECT = CM.parent
PHASE = CM / "_m2_codex_implementation_20260910"
RUN_ID = "ths_v2_20260910_041710_97ef9c09"
RUN = PHASE / "staging_runs" / RUN_ID / f"run_{RUN_ID}"
PARSER = PROJECT / "backend/app/data/tonghuasun_history.py"
PARSER_PIN = "605d65965b1aee56f0f64c5c2446078aefa8d237d7a3d09b5f7403e4a24c2779"
CONTROL = {"SH600011": {"0": 3, "1": 4, "2": 5}, "BJ920000": {"0": 6, "1": 7, "2": 8}}
NUM = ("open", "high", "low", "close", "volume", "amount")


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def D(x):
    return Decimal(str(x))


def ro(path):
    conn = sqlite3.connect("file:" + quote(Path(path).as_posix(), safe="/:") + "?mode=ro", uri=True)
    conn.execute("PRAGMA query_only=ON")
    return conn


def load_parser():
    assert sha(PARSER) == PARSER_PIN
    spec = importlib.util.spec_from_file_location("ths_history_pure2", PARSER)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["ths_history_pure2"] = mod
    spec.loader.exec_module(mod)
    return mod


def main():
    parser = load_parser()
    prior = json.load(open(PHASE / "qualification_pilot52.json", encoding="utf-8"))
    qual = json.load(open(PHASE / "qualification_v2_reviewed.json", encoding="utf-8"))
    out = {"problems": [], "controls": {}, "opened": []}
    plan = json.load(open(PHASE / "qualification_capture/plan.json", encoding="utf-8"))
    jobs = {j["id"]: j for j in plan["jobs"]}

    # ---- (a) cash-forward controls, own implementation
    for sym, modes in CONTROL.items():
        series = {}
        for mode, n in modes.items():
            job = jobs[n]
            assert job["symbol"] == sym and job["payload"]["adjustment"] == int(mode), "control plan mismatch"
            raw = PHASE / f"qualification_capture/response_{n}.bin"
            spec = parser.SecuritySpec.stock(sym)
            dec = parser.parse_history_response(raw.read_bytes(), spec, "2022-08-24", "2026-09-04")
            series[mode] = {r["date"]: r for r in dec["rows"]}
        common = sorted(set(series["0"]) & set(series["1"]) & set(series["2"]))
        events = [e for e in prior["official_cash_events"] if e["symbol"] == sym]
        ev_ok = []
        for e in events:
            p = Path(e["document_path"])
            ev_ok.append({"ex_date": e["ex_date"], "cash": e["cash_per_share_CNY"], "doc_exists": p.is_file(),
                          "doc_hash_match": p.is_file() and sha(p) == e["document_sha256"], "doc": p.name})
        parsed = sorted((e["ex_date"], D(e["cash_per_share_CNY"])) for e in events)
        mism, boundaries = [], []
        va_diff_01, va_diff_02, price_diff_01, price_diff_02 = 0, 0, 0, 0
        for i, day in enumerate(common):
            expected = sum((c for ex, c in parsed if day < ex), Decimal(0))
            for k in ("open", "high", "low", "close"):
                actual = D(series["0"][day][k]) - D(series["1"][day][k])
                if actual != expected:
                    mism.append({"date": day, "field": k, "expected": str(expected), "actual": str(actual)})
            for k in ("volume", "amount"):
                if D(series["0"][day][k]) != D(series["1"][day][k]): va_diff_01 += 1
                if D(series["0"][day][k]) != D(series["2"][day][k]): va_diff_02 += 1
            if any(D(series["0"][day][k]) != D(series["1"][day][k]) for k in ("open", "high", "low", "close")): price_diff_01 += 1
            if any(D(series["0"][day][k]) != D(series["2"][day][k]) for k in ("open", "high", "low", "close")): price_diff_02 += 1
            if any(day == ex for ex, _ in parsed) and i > 0:
                prev = common[i - 1]
                left = D(series["0"][prev]["close"]) - D(series["1"][prev]["close"])
                right = D(series["0"][day]["close"]) - D(series["1"][day]["close"])
                boundaries.append({"ex_date": day, "previous": prev, "observed_cash_step": str(left - right)})
        rec = {"common_dates": len(common), "ohlc_checks": len(common) * 4, "mismatches": mism[:10], "mismatch_count": len(mism),
               "events": ev_ok, "boundaries": boundaries,
               "volume_amount_dates_differing_0_vs_1": va_diff_01, "volume_amount_dates_differing_0_vs_2": va_diff_02,
               "price_dates_differing_0_vs_1": price_diff_01, "price_dates_differing_0_vs_2": price_diff_02,
               "rows_per_mode": {m: len(s) for m, s in series.items()},
               "control_result_in_bundle": qual["controls"][sym]["status"]}
        rec["pass"] = (not mism and va_diff_01 == 0 and va_diff_02 == 0 and price_diff_01 > 0 and price_diff_02 > 0
                       and all(e["doc_hash_match"] for e in ev_ok))
        if not rec["pass"]:
            out["problems"].append(f"control_failed:{sym}")
        # ---- (b) mode-0 control equals staged corpus rows on common dates
        conn = ro(RUN / "trading.sqlite3"); out["opened"].append(str(RUN / "trading.sqlite3"))
        try:
            staged = {d: (o, h, l, c, v, a) for d, o, h, l, c, v, a in conn.execute(
                "SELECT trade_date,open,high,low,close,volume,amount FROM daily_bar_cache WHERE symbol=?", (sym,))}
        finally:
            conn.close()
        same = sum(1 for d in staged if d in series["0"] and tuple(series["0"][d][f] for f in NUM) == staged[d])
        rec["staged_rows"] = len(staged); rec["staged_rows_equal_mode0_control"] = same
        rec["staged_rows_missing_from_mode0"] = sorted(d for d in staged if d not in series["0"])[:5]
        if same != len(staged):
            out["problems"].append(f"staged_ne_mode0:{sym}")
        out["controls"][sym] = rec

    # ---- (c) native depth > 500
    depth = {}
    for scope in qual["scopes"]:
        depth[scope["symbol"]] = max(c["rows"] for c in scope["captures"])
    out["native_depth"] = {"max_rows_single_capture": max(depth.values()), "captures_over_500": sum(1 for v in depth.values() if v > 500),
                           "symbols": len(depth), "min_rows": min(depth.values()),
                           "note": "each retained response is one request; rows > 500 in a single body contradicts a 500-row cap on this interface"}

    # ---- (d) unit anchors
    anchors = json.load(open(PHASE / "unit_anchor_evidence.json", encoding="utf-8"))
    out["unit_anchor_file_sha256"] = sha(PHASE / "unit_anchor_evidence.json")
    out["unit_anchors"] = []
    conn = ro(RUN / "trading.sqlite3")
    try:
        for a in anchors.get("anchors", anchors if isinstance(anchors, list) else []):
            sym, day = a.get("symbol"), a.get("date")
            if not sym or not day:
                continue
            day_iso = day if "-" in day else f"{day[:4]}-{day[4:6]}-{day[6:]}"
            row = conn.execute("SELECT volume, amount FROM daily_bar_cache WHERE symbol=? AND trade_date=?", (sym, day_iso)).fetchone()
            rec = {"symbol": sym, "date": day_iso, "field": a.get("field"), "official": a.get("official_decimal") or a.get("official"),
                   "staged": None if row is None else (str(D(row[0])) if a.get("field") == "volume" else str(D(row[1])))}
            if rec["official"] is not None and rec["staged"] is not None:
                rec["exact_equal"] = D(rec["official"]) == D(rec["staged"])
                rec["difference_staged_minus_official"] = str(D(rec["staged"]) - D(rec["official"]))
                rec["relative_difference"] = str((D(rec["staged"]) - D(rec["official"])) / D(rec["official"]))
            out["unit_anchors"].append(rec)
    finally:
        conn.close()

    # ---- (e) BJ920006 block scope arithmetic
    conn = ro(RUN / "trading.sqlite3")
    try:
        o, h, l, c, v, a = conn.execute("SELECT open,high,low,close,volume,amount FROM daily_bar_cache WHERE symbol='BJ920006' AND trade_date='2023-12-04'").fetchone()
        pc = conn.execute("SELECT close FROM daily_bar_cache WHERE symbol='BJ920006' AND trade_date='2023-12-01'").fetchone()[0]
    finally:
        conn.close()
    bv, bp = D(400000), D("9.25")
    ba = bv * bp
    total_avg = D(a) / D(v)
    resid_v, resid_a = D(v) - bv, D(a) - ba
    resid_avg = resid_a / resid_v
    lo, hi = D(l), D(h)
    out["bj920006_20231204"] = {
        "stored": {"open": o, "high": h, "low": l, "close": c, "volume": v, "amount": a, "previous_close_20231201": pc},
        "block": {"volume_shares": str(bv), "price_CNY": str(bp), "amount_CNY": str(ba)},
        "whole_day_average": str(total_avg), "p4_lower_098xlow": str(lo * D("0.98")), "p4_upper_102xhigh": str(hi * D("1.02")),
        "whole_day_inside_p4_envelope": lo * D("0.98") <= total_avg <= hi * D("1.02"),
        "residual_volume": str(resid_v), "residual_amount": str(resid_a), "residual_average": str(resid_avg),
        "residual_inside_p4_envelope": lo * D("0.98") <= resid_avg <= hi * D("1.02"),
        "residual_strictly_inside_auction_low_high": lo <= resid_avg <= hi,
        "block_share_of_volume": str(bv / D(v)), "block_share_of_amount": str(ba / D(a)),
        "block_price_within_30pct_of_previous_close": D(pc) * D("0.7") <= bp <= D(pc) * D("1.3"),
        "block_price_below_auction_low": bp < lo,
        "whole_day_average_below_auction_low": total_avg < lo,
        "official_daily_total_for_837006_retained": False,
        "bundle_residual_average": [x for s in qual["scopes"] if s["symbol"] == "BJ920006" for x in s["price_domain_exceptions"]],
    }
    json.dump(out, open(HERE / "r06_basis_unit_controls.json", "w", encoding="utf-8"), indent=2, ensure_ascii=False, default=str)
    for sym, r in out["controls"].items():
        print(f"{sym}: common={r['common_dates']} ohlc_checks={r['ohlc_checks']} mismatches={r['mismatch_count']} va_diff01={r['volume_amount_dates_differing_0_vs_1']} va_diff02={r['volume_amount_dates_differing_0_vs_2']} "
              f"price_diff01={r['price_dates_differing_0_vs_1']} price_diff02={r['price_dates_differing_0_vs_2']} PASS={r['pass']} bundle={r['control_result_in_bundle']}")
        print("   boundaries:", r["boundaries"]); print("   events:", [(e['ex_date'], e['cash'], e['doc_hash_match']) for e in r["events"]])
        print(f"   staged rows {r['staged_rows']} equal to mode-0 control: {r['staged_rows_equal_mode0_control']} missing_from_mode0={r['staged_rows_missing_from_mode0']}")
    print("native depth:", out["native_depth"])
    for a in out["unit_anchors"]:
        print("anchor:", a)
    b = out["bj920006_20231204"]
    print("BJ920006 2023-12-04:", {k: v for k, v in b.items() if k not in ("stored", "bundle_residual_average")})
    print("   bundle exception:", b["bundle_residual_average"])
    print("problems:", out["problems"])
    return 0 if not out["problems"] else 1


if __name__ == "__main__":
    sys.exit(main())
