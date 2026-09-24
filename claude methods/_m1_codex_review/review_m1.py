"""Independent M1 spot checks. Stdlib only; production connections are read-only.

Run from the workspace with backend/.venv/Scripts/python.exe -X utf8.
Prints evidence to stdout; never initializes application storage or writes data.
"""
from pathlib import Path
import bisect
import csv
import hashlib
import json
import sqlite3
import statistics

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "claude methods" / "_m1_evidence"
W0, W1 = "2023-09-04", "2026-09-04"


def emit(key, value):
    print(json.dumps({key: value}, ensure_ascii=False), flush=True)


def signature():
    return {p.name: {"bytes": p.stat().st_size, "mtime_ns": p.stat().st_mtime_ns}
            for name in ("trading_local.sqlite3", "market_history.sqlite3")
            for p in (ROOT / name, ROOT / (name + "-wal")) if p.exists()}


def query(con, key, sql, params=()):
    rows = [dict(r) for r in con.execute(sql, params)]
    emit(key, rows)
    return rows


def probe_acceptance_gates():
    """Demonstrate blind spots in the delivered queries, not fixed production code."""
    suite = (EVIDENCE / "backfill_acceptance.sql").read_text(encoding="utf-8")
    def select_between(start, stop, keyword):
        section = suite.split(start, 1)[1].split(stop, 1)[0]
        return section[section.index(keyword):]
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    c.execute("""CREATE TABLE daily_bar_cache(symbol TEXT,trade_date TEXT,
                 open REAL,high REAL,low REAL,close REAL,volume REAL,
                 source TEXT,quality_status TEXT,adjustment_mode TEXT,volume_unit TEXT)""")
    # Unsupported exchange, impossible date, and a deliberately misdeclared unit.
    # All prices remain plausible. Same-source rows remove boundary evidence.
    c.executemany("INSERT INTO daily_bar_cache VALUES(?,?,?,?,?,?,?,?,?,?,?)", [
        ("XX123456", "2025-02-30", 10, 10, 10, 10, 100000, "single_provider", "ready", "qfq", "hand"),
        ("XX123456", "2025-03-03", 10, 10, 10, 10, 100000, "single_provider", "ready", "qfq", "hand"),
    ])
    for name, end in (("V1", "V2"), ("V2", "V3"), ("V3", "V5")):
        query(c, "synthetic_gate_" + name,
              select_between("-- " + name + " ", "-- " + end + " ", "SELECT"))
    query(c, "synthetic_single_source_unit_gate",
          select_between("-- V5b ", "-- V5c ", "WITH b"))
    c.close()


def main():
    before = signature()
    emit("database_files_before", before)
    calendar_path = ROOT / "backend/.venv/Lib/site-packages/akshare/file_fold/calendar.json"
    calendar_bytes = calendar_path.read_bytes()
    dates = sorted({f"{v[:4]}-{v[4:6]}-{v[6:8]}" for v in json.loads(calendar_bytes)})
    window = [d for d in dates if W0 <= d <= W1]
    emit("calendar", {"sha256": hashlib.sha256(calendar_bytes).hexdigest(),
         "sessions": len(window), "head_gap": sum(W0 <= d < "2024-04-09" for d in dates),
         "dense": sum("2024-06-24" <= d <= "2026-09-03" for d in dates),
         "warmup_250_start": dates[bisect.bisect_left(dates, W0) - 250]})
    con = sqlite3.connect((ROOT / "trading_local.sqlite3").as_uri() + "?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    con.execute("ATTACH DATABASE ? AS mh", ((ROOT / "market_history.sqlite3").as_uri() + "?mode=ro",))
    con.execute("PRAGMA query_only=ON")
    con.execute("BEGIN")
    for table in ("daily_bar_cache", "mh.daily_bars"):
        query(con, table, f"""SELECT COUNT(*) n, COUNT(DISTINCT symbol) symbols,
              MIN(trade_date) first_date, MAX(trade_date) last_date,
              COUNT(DISTINCT trade_date) sessions,
              SUM(trade_date < '2023-09-04') warmup,
              SUM(trade_date BETWEEN '2023-09-04' AND '2024-04-08') head_gap
              FROM {table} WHERE trade_date GLOB '????-??-??'""")
    query(con, "inventory", """SELECT COUNT(*) instruments,
          SUM(delist_date IS NOT NULL) delist_dates, SUM(list_date IS NULL) null_list,
          SUM(status='inactive') inactive FROM mh.instruments""")
    query(con, "snapshot_dates", """SELECT COUNT(DISTINCT snapshot_date) n,
          MIN(snapshot_date) first_date, MAX(snapshot_date) last_date FROM mh.universe_snapshots""")
    query(con, "ingest_lineage", "SELECT provider, COUNT(*) n FROM mh.ingest_runs GROUP BY provider")
    query(con, "pricing_anomalies", """SELECT
          SUM(high<low OR high<open OR high<close OR low>open OR low>close) bad_ohlc,
          SUM(trade_date NOT GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]') bad_dates,
          SUM(symbol NOT GLOB '[A-Z][A-Z][0-9][0-9][0-9][0-9][0-9][0-9]') bad_symbol_rows
          FROM daily_bar_cache""")
    query(con, "cross_store_close", """SELECT COUNT(*) joined,
          SUM(c.quality_status='ready' AND c.adjustment_mode='qfq') ready_qfq,
          SUM(c.close IS NULL) cache_close_null,
          SUM(ABS(c.close-h.close)>0.005) absolute_diff,
          SUM(ABS(c.close-h.close)/NULLIF(c.close,0)>0.01) relative_using_cache,
          SUM(ABS(c.close-h.close)/NULLIF(h.close,0)>0.01) relative_using_history,
          SUM(c.quality_status='ready' AND c.adjustment_mode='qfq'
              AND ABS(c.close-h.close)/NULLIF(h.close,0)>0.01) ready_relative_using_history
          FROM daily_bar_cache c JOIN mh.daily_bars h USING(symbol,trade_date)""")
    query(con, "availability", """SELECT COUNT(*) n,
          SUM(available_at<>fetched_at) different,
          COUNT(DISTINCT SUBSTR(fetched_at,1,10)) fetch_days,
          SUM(available_at<='2026-06-30' AND trade_date<='2026-06-30') visible_at_june30
          FROM mh.daily_bars""")
    query(con, "legacy_runs", """SELECT COUNT(*) n,
          SUM(final_cash=initial_cash) unchanged_cash,
          (SELECT COUNT(*) FROM historical_backtest_trades) trade_rows
          FROM historical_backtest_runs""")
    query(con, "ledger_counts", """SELECT
          (SELECT COUNT(*) FROM forecast_decisions) decisions,
          (SELECT COUNT(*) FROM forecast_outcomes) outcomes,
          (SELECT COUNT(*) FROM forecast_evaluations) evaluations,
          (SELECT COUNT(*) FROM forecast_decision_days) claims""")
    emit("evaluation_columns", [r[1] for r in con.execute("PRAGMA table_info(forecast_evaluations)")])
    query(con, "volume_boundaries", """WITH b AS (
          SELECT source, volume, close,
          LAG(source) OVER w previous_source, LAG(volume) OVER w previous_volume,
          LAG(close) OVER w previous_close FROM daily_bar_cache
          WHERE quality_status='ready' AND adjustment_mode='qfq' AND volume>0
          AND length(trade_date)=10 WINDOW w AS (PARTITION BY symbol ORDER BY trade_date))
          SELECT SUM(source<>previous_source) boundaries,
          SUM(source<>previous_source AND previous_volume/volume BETWEEN 20 AND 500) drop20_500,
          SUM(source<>previous_source AND previous_volume/volume BETWEEN 80 AND 130) drop80_130,
          SUM(source=previous_source AND previous_volume/volume BETWEEN 80 AND 130) controls80_130
          FROM b WHERE previous_source IS NOT NULL""")
    query(con, "suspect_tencent", """SELECT COUNT(*) n, COUNT(DISTINCT symbol) symbols,
          SUM(amount IS NULL) amount_null FROM daily_bar_cache WHERE source LIKE '%tencent%'""")
    with (EVIDENCE / "coverage_manifest.csv").open(encoding="utf-8-sig", newline="") as f:
        manifest = {r["symbol"]: r for r in csv.DictReader(f)}
    with (EVIDENCE / "coverage_gap_shape.csv").open(encoding="utf-8-sig", newline="") as f:
        gaps = {r["symbol"]: r for r in csv.DictReader(f)}
    mismatch = []
    for symbol, row in gaps.items():
        m = manifest.get(symbol)
        if m and m.get("eligible_sessions_calendar"):
            claimed = int(m["eligible_sessions_calendar"])
            if row.get("eligible_sessions") and claimed != int(row["eligible_sessions"]):
                mismatch.append(symbol)
    ratios, prewindow, errors = [], [], []
    for row in con.execute("SELECT symbol,list_date,delist_date FROM mh.instruments WHERE list_date IS NOT NULL"):
        symbol, start, end = row
        eligible = sum(max(start, W0) <= d <= min(end or W1, W1) for d in window)
        m = manifest.get(symbol)
        if m and eligible:
            if int(m["eligible_sessions_calendar"]) != eligible:
                errors.append(symbol)
            ratio = int(m["observed_sessions"]) / eligible
            ratios.append(ratio)
            if start <= W0:
                prewindow.append(ratio)
    emit("manifest_reconciliation", {"manifest_rows": len(manifest), "gap_rows": len(gaps),
         "calendar_denominator_errors": errors, "ratio_count": len(ratios),
         "median": statistics.median(ratios), "prewindow_count": len(prewindow),
         "prewindow_max": max(prewindow), "prewindow_at_least_95pct": sum(v >= .95 for v in prewindow),
         "gap_denominator_disagreements": len(mismatch),
         "example_manifest": manifest["BJ920000"], "example_gap": gaps["BJ920000"]})
    baseline = json.loads((EVIDENCE / "backfill_acceptance_BEFORE.json").read_text(encoding="utf-8-sig"))
    emit("frozen_baseline_keys", list(baseline))
    con.rollback()
    con.close()
    after = signature()
    emit("database_files_after", after)
    emit("main_and_wal_metadata_unchanged", before == after)
    probe_acceptance_gates()


if __name__ == "__main__":
    main()
