"""R4 - deterministic stratified 50-stock pilot selection (+ benchmark).

Selection is read-only and fully deterministic: every stratum is ordered by an explicit
key and truncated, so re-running reproduces the identical list. No randomness, no
network, nothing downloaded. This proposes WHICH symbols a pilot would fetch if the user
authorizes one; it does not fetch anything.

Strata exist to make the pilot capable of FAILING in each way the audit found the data
can be wrong, rather than confirming the easy cases:

  ordinary_control      the boring case; if these break, the pipeline is broken
  suspected_unit_switch a ~100x volume step at a provider boundary (the 股/手 finding)
  ipo_in_window         listing inside the window; short eligible interval
  bj_code_history       BJ 920xxx, where pre-2024-08-12 history sits under old codes
  largest_interior_gap  the interior holes whose cause is unknown
"""

from __future__ import annotations

import csv
import io
import json
import sqlite3
from pathlib import Path

ROOT = Path(r"D:\codex-A股交易")
TRADING = ROOT / "trading_local.sqlite3"
OUT = ROOT / "claude methods/_m1_closure"

WINDOW_START, WINDOW_END = "2023-09-04", "2026-09-04"
BENCHMARKS = ["SH000300", "SH000001"]
QUOTA = {
    "ordinary_control": 20,
    "suspected_unit_switch": 10,
    "ipo_in_window": 8,
    "bj_code_history": 7,
    "largest_interior_gap": 5,
}


def ro(path):
    conn = sqlite3.connect("file:%s?mode=ro" % path, uri=True)
    conn.execute("PRAGMA query_only=1")
    conn.row_factory = sqlite3.Row
    return conn


def load_coverage():
    path = OUT / "coverage_reconciled.csv"
    with io.open(path, encoding="utf-8") as fh:
        return {r["symbol"]: r for r in csv.DictReader(fh)}


def suspected_unit_switch(conn, limit):
    """Symbols showing a ~100x volume step exactly at a provider change.

    This is a SUSPICION used to target the pilot, never a correction. No row is rescaled
    anywhere in this project on the strength of it.
    """
    rows = conn.execute("""
        WITH b AS (
          SELECT symbol, trade_date, source, volume,
                 LAG(source) OVER (PARTITION BY symbol ORDER BY trade_date) ps,
                 LAG(volume) OVER (PARTITION BY symbol ORDER BY trade_date) pv
          FROM daily_bar_cache
          WHERE quality_status='ready' AND adjustment_mode='qfq' AND volume > 0
            AND trade_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'
        )
        SELECT symbol, MIN(trade_date) boundary_date, MAX(pv/volume) ratio
        FROM b
        WHERE ps IS NOT NULL AND source <> ps AND pv/volume BETWEEN 80 AND 130
        GROUP BY symbol ORDER BY symbol
    """).fetchall()
    # MEASURED: all 293 such events are SH688xxx (STAR board), 293 distinct symbols,
    # every one a tencent.fqkline -> akshare.stock_zh_a_daily transition, and 218 of the
    # 293 land on 2024-08-13. The stratum is single-board because the EVIDENCE is
    # single-board, not because the selector truncated alphabetically. The even stride
    # below therefore spreads across the 293 rather than taking the head of the list.
    #
    # Consequence for scope: this evidences 293 STAR-board symbols. It does NOT evidence
    # the 306,543-row / 4,946-symbol tencent population, which remains UNVERIFIABLE and
    # quarantined (gate D4). A plausible mechanism is the STAR board's different lot
    # convention, but that is a hypothesis for the pilot to test, not a finding.
    # Deterministic: same input list, same indices, same picks.
    if not rows:
        return []
    step = max(1, len(rows) // limit)
    picked = [rows[i] for i in range(0, len(rows), step)][:limit]
    return [(r["symbol"], "boundary=%s ratio=%.1f" % (r["boundary_date"], r["ratio"]))
            for r in picked]


def select():
    conn = ro(TRADING)
    cov = load_coverage()
    chosen, used = [], set()

    def take(stratum, candidates, note_fn):
        n = 0
        for sym in candidates:
            if n >= QUOTA[stratum] or sym in used:
                continue
            row = cov.get(sym)
            if not row:
                continue
            used.add(sym)
            chosen.append({
                "symbol": sym, "stratum": stratum, "name": row["name"],
                "exchange": row["exchange"], "list_date": row["list_date"],
                "eligible_sessions": int(row["eligible_sessions"]),
                "observed_sessions": int(row["observed_sessions"]),
                "leading_gap": int(row["leading_gap"]),
                "interior_gap": int(row["interior_gap"]),
                "trailing_gap": int(row["trailing_gap"]),
                "coverage_ratio": row["coverage_ratio"],
                "selection_note": note_fn(sym),
            })
            n += 1
        return n

    # 1. suspected unit switch - the targeted defect, chosen first so it is never crowded out
    susp = suspected_unit_switch(conn, QUOTA["suspected_unit_switch"])
    notes = dict(susp)
    take("suspected_unit_switch", [s for s, _ in susp], lambda s: notes.get(s, ""))

    # 2. BJ code history
    bj = sorted(s for s, r in cov.items()
                if r["exchange"] == "BJ" and s.startswith("BJ920"))
    take("bj_code_history", bj,
         lambda s: "pre-2024-08-12 history expected under an 8xxxxx code; mapping unknown")

    # 3. IPO inside the window
    ipo = sorted((r["list_date"], s) for s, r in cov.items()
                 if r["list_date"] and WINDOW_START < r["list_date"] <= WINDOW_END)
    take("ipo_in_window", [s for _, s in ipo],
         lambda s: "listed %s; short eligible interval" % cov[s]["list_date"])

    # 4. largest interior gaps
    holes = sorted(((-int(r["interior_gap"]), s) for s, r in cov.items()
                    if int(r["interior_gap"]) > 0))
    take("largest_interior_gap", [s for _, s in holes],
         lambda s: "interior_gap=%s sessions, cause unknown" % cov[s]["interior_gap"])

    # 5. ordinary controls - highest coverage, listed before the window, spread across
    #    exchanges so the control group is not accidentally all one venue
    ordinary = sorted(
        (s for s, r in cov.items()
         if r["list_date"] and r["list_date"] <= WINDOW_START
         and r["coverage_ratio"] and int(r["interior_gap"]) == 0),
        key=lambda s: (-float(cov[s]["coverage_ratio"]), s))
    balanced, seen_ex = [], {}
    for s in ordinary:
        ex = cov[s]["exchange"]
        if seen_ex.get(ex, 0) >= QUOTA["ordinary_control"] // 2:
            continue
        seen_ex[ex] = seen_ex.get(ex, 0) + 1
        balanced.append(s)
    take("ordinary_control", balanced + ordinary,
         lambda s: "coverage=%s, no interior gap" % cov[s]["coverage_ratio"])

    conn.close()
    return chosen


if __name__ == "__main__":
    picks = select()
    OUT.mkdir(parents=True, exist_ok=True)
    # Benchmarks are emitted into the SAME manifest with stratum='benchmark', so the
    # staging gate can route stock and benchmark populations from one supplied file
    # without any caller re-deriving the split (F4).
    rows = list(picks)
    for mark in BENCHMARKS:
        blank = {k: "" for k in picks[0]}
        blank.update({"symbol": mark, "stratum": "benchmark", "exchange": "INDEX",
                      "selection_note": "index benchmark; not a stock, no liquidity "
                                        "evidence required"})
        rows.append(blank)
    with io.open(OUT / "pilot_symbols.csv", "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(picks[0].keys()))
        w.writeheader()
        w.writerows(rows)
    (OUT / "pilot_symbols_meta.json").write_text(json.dumps({
        "window": [WINDOW_START, WINDOW_END],
        "benchmarks": BENCHMARKS,
        "quota": QUOTA,
        "selected": len(picks),
        "deterministic": True,
        "authorization": "PROPOSAL ONLY - no download performed or authorized",
    }, indent=2, ensure_ascii=False), encoding="utf-8")

    by = {}
    for p in picks:
        by.setdefault(p["stratum"], []).append(p["symbol"])
    print("stratified pilot selection (proposal only, nothing fetched)")
    for stratum, quota in QUOTA.items():
        got = by.get(stratum, [])
        print("  %-22s %2d/%d  %s" % (stratum, len(got), quota, ", ".join(got[:6]) +
                                      (" ..." if len(got) > 6 else "")))
    print("  %-22s %2d      %s" % ("benchmark", len(BENCHMARKS), ", ".join(BENCHMARKS)))
    print("  total stocks: %d" % len(picks))
