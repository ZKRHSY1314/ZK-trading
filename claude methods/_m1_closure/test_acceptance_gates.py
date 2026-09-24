"""R3 - synthetic regression set proving each gate can FAIL.

A gate that has never been shown to reject a bad input is not evidence. Codex
demonstrated that the superseded V2/V3/V5b/V7 all reported "0 violations" on inputs that
were definitely wrong, which is indistinguishable from a clean result.

Every case below builds a tiny in-memory database containing exactly one defect, runs
the corresponding gate, and asserts the expected outcome - including that the CLEAN
control passes, so the gates are not merely always-FAIL.

No production database is opened. Run: python test_acceptance_gates.py
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from acceptance_runner import (  # noqa: E402
    FAIL, PASS, UNKNOWN, archive_fingerprint, chk_archive, chk_cross_store, chk_dates,
    chk_duplicates, chk_population, chk_prices, chk_provenance, chk_symbols, chk_units,
)

CACHE_DDL = """
CREATE TABLE daily_bar_cache (
    symbol TEXT, trade_date TEXT, open REAL, high REAL, low REAL, close REAL,
    volume REAL, amount REAL, source TEXT, quality_status TEXT,
    adjustment_mode TEXT DEFAULT 'unknown', volume_unit TEXT DEFAULT 'unknown'
);
CREATE TABLE instruments (symbol TEXT PRIMARY KEY, name TEXT);
"""
BARS_DDL = """
CREATE TABLE daily_bars (
    symbol TEXT, trade_date TEXT, adjustment_mode TEXT, close REAL, volume REAL,
    amount REAL, ingest_run_id INTEGER
);
CREATE TABLE ingest_runs (id INTEGER PRIMARY KEY, provider TEXT);
"""

# A real session from the pinned calendar, so clean controls are genuinely clean.
GOOD_DATE = "2025-06-10"


def db(ddl):
    conn = sqlite3.connect("file::memory:", uri=True)
    conn.row_factory = sqlite3.Row
    conn.executescript(ddl)
    return conn


def cache_row(conn, symbol="SZ000001", date=GOOD_DATE, o=10.0, h=11.0, low=9.0, c=10.5,
              vol=1000.0, amount=None, source="sina", adj="none", unit="hand",
              register=True):
    conn.execute(
        "INSERT INTO daily_bar_cache VALUES (?,?,?,?,?,?,?,?,?,'ready',?,?)",
        (symbol, date, o, h, low, c, vol, amount, source, adj, unit))
    if register:
        conn.execute("INSERT OR IGNORE INTO instruments VALUES (?, 'fixture')", (symbol,))


CASES = []


def case(name, expect):
    def deco(fn):
        CASES.append((name, expect, fn))
        return fn
    return deco


# ------------------------------------------------------------------ impossible dates
@case("D1 clean control: a real trading session passes", PASS)
def _(conn=None):
    conn = db(CACHE_DDL); cache_row(conn)
    return chk_dates(conn)


@case("D1 impossible date 2025-02-30 is caught (shape alone passed before)", FAIL)
def _():
    conn = db(CACHE_DDL); cache_row(conn, date="2025-02-30")
    return chk_dates(conn)


@case("D1 real date that is not an exchange session is caught", FAIL)
def _():
    conn = db(CACHE_DDL); cache_row(conn, date="2025-06-08")  # a Sunday
    return chk_dates(conn)


@case("D1 malformed sentinel ERROR is caught", FAIL)
def _():
    conn = db(CACHE_DDL); cache_row(conn, date="ERROR")
    return chk_dates(conn)


# --------------------------------------------------------------- unsupported symbols
@case("D2 clean control: a registered SZ symbol passes", PASS)
def _():
    conn = db(CACHE_DDL); cache_row(conn)
    return chk_symbols(conn)


@case("D2 unsupported namespace XX123456 is caught (shape alone passed before)", FAIL)
def _():
    conn = db(CACHE_DDL); cache_row(conn, symbol="XX123456")
    return chk_symbols(conn)


@case("D2 bare 6-digit symbol is caught", FAIL)
def _():
    conn = db(CACHE_DDL); cache_row(conn, symbol="000001")
    return chk_symbols(conn)


@case("D2 well-formed symbol absent from instruments is caught", FAIL)
def _():
    conn = db(CACHE_DDL); cache_row(conn, symbol="SZ999999", register=False)
    return chk_symbols(conn)


# ------------------------------------------------------- missing / nonpositive prices
@case("D3 clean control passes", PASS)
def _():
    conn = db(CACHE_DDL); cache_row(conn)
    return chk_prices(conn)


@case("D3 NULL close is caught", FAIL)
def _():
    conn = db(CACHE_DDL); cache_row(conn, c=None)
    return chk_prices(conn)


@case("D3 nonpositive close is caught", FAIL)
def _():
    conn = db(CACHE_DDL); cache_row(conn, c=0.0)
    return chk_prices(conn)


@case("D3 high < low is caught", FAIL)
def _():
    conn = db(CACHE_DDL); cache_row(conn, h=8.0, low=9.0, o=8.5, c=8.5)
    return chk_prices(conn)


# ------------------------------------------------------------ wrong or unknown units
@case("D4 clean control: hand units consistent with amount pass", PASS)
def _():
    conn = db(CACHE_DDL)
    # 1000 hands x 100 shares x 10.5 = 1,050,000
    cache_row(conn, vol=1000.0, amount=1_050_000.0, unit="hand", adj="none")
    return chk_units(conn)


@case("D4 SAME-SOURCE wrong unit is caught with NO provider boundary present", FAIL)
def _():
    conn = db(CACHE_DDL)
    # Declared 'hand' but the amount only supports 'share'. One source, no boundary:
    # this is exactly the fixture on which the superseded V5b reported zero violations.
    cache_row(conn, vol=1000.0, amount=10_500.0, unit="hand", adj="none", source="sina")
    return chk_units(conn)


@case("D4 unsupported declared unit is missing evidence, not a contradiction", UNKNOWN)
def _():
    # Expectation deliberately changed in the F2 pass. A declared unit of 'unknown' is
    # ABSENT evidence, not a contradicted measurement, so UNKNOWN is the honest outcome
    # and collapsing it to FAIL would lose that distinction. UNKNOWN still cannot pass.
    conn = db(CACHE_DDL)
    cache_row(conn, vol=1000.0, amount=1_050_000.0, unit="unknown", adj="none")
    return chk_units(conn)


@case("D4 unverifiable population is QUARANTINED as UNKNOWN, never PASS", UNKNOWN)
def _():
    conn = db(CACHE_DDL)
    # qfq price with raw amount: no common basis, so no valid comparison exists.
    cache_row(conn, vol=1000.0, amount=1_050_000.0, unit="hand", adj="qfq")
    return chk_units(conn)


# ------------------------------------------------------- invalid provenance reference
@case("D5 clean control: run id resolves", PASS)
def _():
    conn = db(BARS_DDL)
    conn.execute("INSERT INTO ingest_runs VALUES (1, 'sina')")
    conn.execute("INSERT INTO daily_bars VALUES ('SZ000001', ?, 'qfq', 10.5, 1000, NULL, 1)", (GOOD_DATE,))
    return chk_provenance(conn)


@case("D5 dangling non-NULL run id is caught (NULL-only check passed before)", FAIL)
def _():
    conn = db(BARS_DDL)
    conn.execute("INSERT INTO ingest_runs VALUES (1, 'sina')")
    conn.execute("INSERT INTO daily_bars VALUES ('SZ000001', ?, 'qfq', 10.5, 1000, NULL, 42)", (GOOD_DATE,))
    return chk_provenance(conn)


@case("D5 missing ingest_runs table is UNKNOWN, not PASS", UNKNOWN)
def _():
    conn = db("CREATE TABLE daily_bars (symbol TEXT, trade_date TEXT, adjustment_mode TEXT,"
              " close REAL, volume REAL, amount REAL, ingest_run_id INTEGER);")
    conn.execute("INSERT INTO daily_bars VALUES ('SZ000001', ?, 'qfq', 10.5, 1000, NULL, 1)", (GOOD_DATE,))
    return chk_provenance(conn)


# ------------------------------------------- archive edited with row count unchanged
def _archive(close_value):
    conn = db(BARS_DDL)
    conn.execute("INSERT INTO ingest_runs VALUES (1, 'sina')")
    for i, sym in enumerate(("SZ000001", "SH600000", "BJ920000")):
        conn.execute("INSERT INTO daily_bars VALUES (?, ?, 'qfq', ?, 1000, NULL, 1)",
                     (sym, GOOD_DATE, close_value + i))
    return conn


@case("D6 clean control: untouched archive matches its fingerprint", PASS)
def _():
    base = archive_fingerprint(_archive(10.0))
    return chk_archive(_archive(10.0), base)


@case("D6 one edited value with IDENTICAL row count is caught", FAIL)
def _():
    base = archive_fingerprint(_archive(10.0))
    tampered = _archive(10.0)
    tampered.execute("UPDATE daily_bars SET close = 99.0 WHERE symbol = 'SH600000'")
    # Row count is unchanged - the superseded V7 compared exactly this and saw nothing.
    assert tampered.execute("SELECT COUNT(*) FROM daily_bars").fetchone()[0] == 3
    return chk_archive(tampered, base)


@case("D6 no frozen baseline is UNKNOWN, not PASS", UNKNOWN)
def _():
    return chk_archive(_archive(10.0), None)


# ============================================================ F2 / F4 regressions
# Each reproduces a false-pass path the Codex closure review demonstrated.

@case("F2a volume_unit=NULL must not PASS (SQL NULL bypassed both tests)", UNKNOWN)
def _():
    conn = db(CACHE_DDL)
    conn.execute(
        "INSERT INTO daily_bar_cache VALUES ('SZ000001',?,10.0,11.0,9.0,10.5,"
        "1000.0,1050000.0,'sina','ready','none',NULL)", (GOOD_DATE,))
    conn.execute("INSERT INTO instruments VALUES ('SZ000001','fixture')")
    return chk_units(conn)


@case("F2b blank volume_unit must not PASS", UNKNOWN)
def _():
    conn = db(CACHE_DDL)
    cache_row(conn, vol=1000.0, amount=1_050_000.0, unit="   ", adj="none")
    return chk_units(conn)


@case("F2c empty table is UNKNOWN for D1, not PASS", UNKNOWN)
def _():
    return chk_dates(db(CACHE_DDL))


@case("F2d empty table is UNKNOWN for D2, not PASS", UNKNOWN)
def _():
    return chk_symbols(db(CACHE_DDL))


@case("F2e empty table is UNKNOWN for D3, not PASS", UNKNOWN)
def _():
    return chk_prices(db(CACHE_DDL))


@case("F2f empty table is UNKNOWN for D5, not PASS", UNKNOWN)
def _():
    return chk_provenance(db(BARS_DDL))


@case("F2g duplicate business keys are caught (check had been dropped)", FAIL)
def _():
    conn = db(CACHE_DDL)
    cache_row(conn); cache_row(conn)
    return chk_duplicates(conn)


@case("F2h clean control: distinct keys pass the duplicate check", PASS)
def _():
    conn = db(CACHE_DDL)
    cache_row(conn, date=GOOD_DATE); cache_row(conn, date="2025-06-11")
    return chk_duplicates(conn)


@case("F2i population gate is UNKNOWN when nothing is declared", UNKNOWN)
def _():
    conn = db(CACHE_DDL); cache_row(conn)
    return chk_population(conn)


@case("F2j population gate FAILs a short batch against the declared expectation", FAIL)
def _():
    conn = db(CACHE_DDL); cache_row(conn)
    return chk_population(conn, expected_symbols=52, expected_sessions=728)


@case("F2k population gate passes when the batch matches", PASS)
def _():
    conn = db(CACHE_DDL)
    cache_row(conn, symbol="SZ000001", date=GOOD_DATE)
    cache_row(conn, symbol="SH600000", date=GOOD_DATE)
    return chk_population(conn, expected_symbols=2, expected_sessions=1)


@case("F2l cross-store comparison refused without a declared transformation", UNKNOWN)
def _():
    conn = db(CACHE_DDL + BARS_DDL)
    cache_row(conn)
    conn.execute("INSERT INTO daily_bars VALUES ('SZ000001',?,'qfq',9.9,1000,NULL,1)", (GOOD_DATE,))
    return chk_cross_store(conn)


@case("F2m declared identity transformation detects a real divergence", FAIL)
def _():
    conn = db(CACHE_DDL + BARS_DDL)
    cache_row(conn, c=10.5)
    conn.execute("INSERT INTO daily_bars VALUES ('SZ000001',?,'none',9.9,1000,NULL,1)", (GOOD_DATE,))
    return chk_cross_store(conn, declared_transformation="identity")


@case("F2n declared identity transformation passes on agreeing values", PASS)
def _():
    conn = db(CACHE_DDL + BARS_DDL)
    cache_row(conn, c=10.5)
    conn.execute("INSERT INTO daily_bars VALUES ('SZ000001',?,'none',10.5,1000,NULL,1)", (GOOD_DATE,))
    return chk_cross_store(conn, declared_transformation="identity")


@case("F4a benchmark passes D2 without being in the stock catalog", PASS)
def _():
    conn = db(CACHE_DDL)
    cache_row(conn, symbol="SH000300", register=False)
    cache_row(conn, symbol="SZ000001")
    return chk_symbols(conn, benchmarks=("SH000300", "SH000001"))


@case("F4b unrouted benchmark still FAILs D2 (routing must be explicit)", FAIL)
def _():
    conn = db(CACHE_DDL)
    cache_row(conn, symbol="SH000300", register=False)
    return chk_symbols(conn)


@case("F4c benchmark-only batch yields no stock unit evidence, not a PASS", UNKNOWN)
def _():
    conn = db(CACHE_DDL)
    cache_row(conn, symbol="SH000300", register=False, amount=None, vol=0.0)
    return chk_units(conn, benchmarks=("SH000300",))


@case("F4d excluding a benchmark cannot hide an unverifiable stock", UNKNOWN)
def _():
    conn = db(CACHE_DDL)
    cache_row(conn, symbol="SH000300", register=False)              # routed away
    cache_row(conn, symbol="SZ000001", amount=None, adj="none")     # genuinely unknown
    return chk_units(conn, benchmarks=("SH000300",))


@case("F4e stocks with raw-basis evidence still PASS alongside a routed benchmark", PASS)
def _():
    conn = db(CACHE_DDL)
    cache_row(conn, symbol="SH000300", register=False)
    cache_row(conn, symbol="SZ000001", vol=1000.0, amount=1_050_000.0,
              unit="hand", adj="none")
    return chk_units(conn, benchmarks=("SH000300",))


FULL_BARS_DDL = """
CREATE TABLE daily_bars (
    symbol TEXT, trade_date TEXT, adjustment_mode TEXT, open REAL, high REAL, low REAL,
    close REAL, volume REAL, amount REAL, provider TEXT, fetched_at TEXT,
    ingest_run_id INTEGER
);
CREATE TABLE ingest_runs (id INTEGER PRIMARY KEY, provider TEXT);
"""


def _full_archive():
    conn = db(FULL_BARS_DDL)
    conn.execute("INSERT INTO ingest_runs VALUES (1, 'sina')")
    for i, sym in enumerate(("SZ000001", "SH600000", "BJ920000")):
        conn.execute(
            "INSERT INTO daily_bars VALUES (?,?,'qfq',?,?,?,?,1000,NULL,'sina',"
            "'2026-06-30T04:55:30+08:00',1)",
            (sym, GOOD_DATE, 10.0 + i, 11.0 + i, 9.0 + i, 10.5 + i))
    return conn


@case("F3a whole-database hash catches an edited OPEN price (narrow hash missed it)", FAIL)
def _():
    # The narrow digest covered only symbol/date/adjustment/close/volume/amount, so an
    # edited open price left it unchanged.
    base = archive_fingerprint(_full_archive())
    t = _full_archive()
    t.execute("UPDATE daily_bars SET open = 99.0 WHERE symbol = 'SH600000'")
    assert t.execute("SELECT COUNT(*) FROM daily_bars").fetchone()[0] == 3
    narrow_same = (archive_fingerprint(t, full=False)
                   == archive_fingerprint(_full_archive(), full=False))
    assert narrow_same, "narrow digest should NOT notice an edited open price"
    return chk_archive(t, base)


@case("F3a2 whole-database hash catches an edited PROVIDER column", FAIL)
def _():
    base = archive_fingerprint(_full_archive())
    t = _full_archive()
    t.execute("UPDATE daily_bars SET provider = 'tampered' WHERE symbol = 'SH600000'")
    return chk_archive(t, base)


@case("F3a3 whole-database hash catches a schema change with identical data", FAIL)
def _():
    base = archive_fingerprint(_full_archive())
    t = _full_archive()
    t.execute("ALTER TABLE daily_bars ADD COLUMN extra REAL")
    return chk_archive(t, base)


@case("F3a4 clean control: untouched full archive matches", PASS)
def _():
    return chk_archive(_full_archive(), archive_fingerprint(_full_archive()))


@case("F3b whole-database hash catches an edited provider in an unrelated table", FAIL)
def _():
    base = archive_fingerprint(_archive(10.0))
    t = _archive(10.0)
    t.execute("UPDATE ingest_runs SET provider = 'tampered'")
    assert t.execute("SELECT COUNT(*) FROM daily_bars").fetchone()[0] == 3
    return chk_archive(t, base)


def main():
    failures = 0
    print("R3 synthetic gate regression set")
    for name, expect, fn in CASES:
        status, observed, detail = fn()
        ok = status == expect
        failures += not ok
        print("  [%s] %-68s expected=%-7s got=%-7s" % (
            "ok" if ok else "XX", name, expect, status))
        if not ok:
            print("        detail: %s" % detail)
    print("\n  %d cases, %d unexpected" % (len(CASES), failures))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
