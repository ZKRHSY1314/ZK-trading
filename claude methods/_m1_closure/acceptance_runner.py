"""R3/F2/F4 - the acceptance check library.

Every gate is a function with explicit routing and a four-valued outcome:

    PASS            evidence exists and satisfies the threshold
    FAIL            evidence exists and violates the threshold
    UNKNOWN         the evidence needed to decide does not exist
    NOT_APPLICABLE  the check is out of scope for this population (benchmarks)

UNKNOWN and NOT_APPLICABLE never count as PASS, and NOT_APPLICABLE is only ever returned
for a population the check was explicitly scoped away from - it can never mask an
unknown in the population the check DOES cover.

What the first Codex review broke (fixed previously)
----------------------------------------------------
Shape-only date/symbol matching, boundary-inferred units, row-count-only archive checks,
NULL-only provenance checks.

What the closure review broke (F2/F4, fixed here)
--------------------------------------------------
* D4 returned PASS for a row with `volume_unit = NULL`. SQL three-valued logic made both
  `volume_unit = 'hand'` and `volume_unit NOT IN ('hand','share')` evaluate to NULL, so
  the row was counted verifiable and never contradicted. A missing unit is MISSING
  EVIDENCE, not a verified unit; it is now quarantined.
* D1/D2/D3/D5 returned PASS on empty tables. Absence of rows is absence of evidence, so
  every check now returns UNKNOWN on an empty population, and a separate population gate
  asserts the expected symbol/session counts before any batch can be called good.
* Duplicate keys were unchecked after the registry was rewritten. Restored as D7.
* No cross-store reconciliation existed. Added as D8 - and it REFUSES to compare a raw
  series against an adjusted one unless a transformation is explicitly declared, rather
  than demanding raw price equality across different bases.
* D2 demanded every symbol be in the stock catalog and D4 demanded trade-capacity
  evidence, so a legitimate index benchmark could not pass. Stock and benchmark
  populations are now routed separately (F4).
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import re
import sqlite3
import sys
from pathlib import Path

ROOT = Path(r"D:\codex-A股交易")
TRADING = ROOT / "trading_local.sqlite3"
HISTORY = ROOT / "market_history.sqlite3"
OUT = ROOT / "claude methods/_m1_closure"

PASS, FAIL, UNKNOWN, NOT_APPLICABLE = "PASS", "FAIL", "UNKNOWN", "NOT_APPLICABLE"
SUCCESSFUL = frozenset({PASS, NOT_APPLICABLE})

STOCK_RE = re.compile(r"^(SH|SZ|BJ)\d{6}$")
BENCHMARKS = ("SH000300", "SH000001")
SUPPORTED_UNITS = ("hand", "share")

sys.path.insert(0, str(Path(__file__).resolve().parent))
from coverage_gap_generator import CALENDAR_SHA256, SESSIONS  # noqa: E402

SESSION_SET = set(SESSIONS)


def ro(path):
    conn = sqlite3.connect("file:%s?mode=ro" % path, uri=True)
    conn.execute("PRAGMA query_only=1")
    conn.row_factory = sqlite3.Row
    return conn


def _is_real_date(value):
    try:
        _dt.date.fromisoformat(value)
        return True
    except (ValueError, TypeError):
        return False


def _readable(conn, name):
    try:
        conn.execute("SELECT 1 FROM %s LIMIT 1" % name).fetchone()
        return True
    except sqlite3.Error:
        return False


def _count(conn, name):
    return conn.execute("SELECT COUNT(*) FROM %s" % name).fetchone()[0]


def _empty_guard(conn, table):
    """Absence of rows is absence of evidence, never a pass."""
    if not _readable(conn, table):
        return UNKNOWN, None, "%s absent or unreadable" % table
    if _count(conn, table) == 0:
        return UNKNOWN, 0, "%s is empty; no evidence to evaluate" % table
    return None


# ------------------------------------------------------------------------- the checks

def chk_dates(conn, table="daily_bar_cache"):
    """D1 impossible and non-session dates. Shape is not validity."""
    guard = _empty_guard(conn, table)
    if guard:
        return guard
    malformed, impossible, non_session = [], [], []
    for (value,) in conn.execute("SELECT DISTINCT trade_date FROM %s" % table):
        text = str(value or "")
        if not re.match(r"^\d{4}-\d{2}-\d{2}$", text):
            malformed.append(value)
        elif not _is_real_date(text):
            impossible.append(value)
        elif text not in SESSION_SET:
            non_session.append(value)
    total = len(malformed) + len(impossible) + len(non_session)
    return (PASS if total == 0 else FAIL), total, (
        "table=%s malformed=%s impossible=%s non_session=%s"
        % (table, malformed[:5], impossible[:5], non_session[:5]))


def chk_symbols(conn, benchmarks=(), table="daily_bar_cache"):
    """D2 namespace and catalog membership, with benchmarks routed separately (F4)."""
    guard = _empty_guard(conn, table)
    if guard:
        return guard
    benchmark_set = set(benchmarks)
    if not _readable(conn, "instruments"):
        return UNKNOWN, None, "instruments catalog not routed; membership undecidable"
    known = {r[0] for r in conn.execute("SELECT symbol FROM instruments")}

    bad_ns, unknown_ref, seen_benchmarks = [], [], []
    for (sym,) in conn.execute("SELECT DISTINCT symbol FROM %s" % table):
        if sym in benchmark_set:
            # A benchmark is not a stock. It is validated for identity only; demanding
            # membership in the stock catalog would force misclassifying an index.
            seen_benchmarks.append(sym)
            continue
        if not STOCK_RE.match(str(sym or "")):
            bad_ns.append(sym)
        elif sym not in known:
            unknown_ref.append(sym)
    total = len(bad_ns) + len(unknown_ref)
    return (PASS if total == 0 else FAIL), total, (
        "bad_namespace=%s not_in_instruments=%s benchmarks_routed=%s"
        % (bad_ns[:5], unknown_ref[:5], seen_benchmarks))


def chk_prices(conn, table="daily_bar_cache"):
    """D3 missing / nonpositive prices and broken OHLC relations."""
    guard = _empty_guard(conn, table)
    if guard:
        return guard
    n = conn.execute(
        "SELECT COUNT(*) FROM %s WHERE "
        "open IS NULL OR high IS NULL OR low IS NULL OR close IS NULL "
        "OR close <= 0 OR open <= 0 OR high <= 0 OR low <= 0 "
        "OR high < low OR high < open OR high < close OR low > open OR low > close"
        % table).fetchone()[0]
    return (PASS if n == 0 else FAIL), n, "table=%s violating rows=%d" % (table, n)


def chk_units(conn, benchmarks=(), table="daily_bar_cache"):
    """D4 stock volume units VERIFIED per row; everything else QUARANTINED.

    Verification requires raw (unadjusted) price alongside a positive amount and volume
    AND a declared, supported unit. Comparing a raw CNY amount against an adjusted price
    is not a valid test, so those rows are quarantined rather than judged.

    Benchmarks are excluded (F4): an index is not traded, so demanding trade-capacity
    evidence from it would either fail a valid benchmark or invent liquidity. Their
    exclusion is reported and can never absorb an unknown among the stocks.
    """
    guard = _empty_guard(conn, table)
    if guard:
        return guard
    marks = list(benchmarks)
    placeholders = ",".join("?" for _ in marks) if marks else "''"
    where_stock = "symbol NOT IN (%s)" % placeholders if marks else "1=1"
    args = marks

    total = conn.execute(
        "SELECT COUNT(*) FROM %s WHERE %s" % (table, where_stock), args).fetchone()[0]
    if total == 0:
        return UNKNOWN, 0, "no stock rows after routing %d benchmark(s)" % len(marks)

    # Verifiable requires a DECLARED SUPPORTED unit. NULL/blank/unsupported is missing
    # evidence: SQL three-valued logic previously let volume_unit=NULL pass both the
    # equality tests and NOT IN, so such a row was silently counted as verified.
    unit_ok = "volume_unit IN (%s)" % ",".join("?" for _ in SUPPORTED_UNITS)
    verifiable_sql = (
        "amount IS NOT NULL AND amount > 0 AND volume IS NOT NULL AND volume > 0 "
        "AND adjustment_mode = 'none' AND volume_unit IS NOT NULL "
        "AND TRIM(volume_unit) <> '' AND " + unit_ok)
    verifiable = conn.execute(
        "SELECT COUNT(*) FROM %s WHERE %s AND %s" % (table, where_stock, verifiable_sql),
        args + list(SUPPORTED_UNITS)).fetchone()[0]
    quarantined = total - verifiable

    contradicted = 0
    if verifiable:
        contradicted = conn.execute(
            "SELECT COUNT(*) FROM %s WHERE %s AND %s AND ("
            "  (volume_unit = 'hand'  AND amount / (volume * 100.0) NOT BETWEEN low*0.98 AND high*1.02) OR"
            "  (volume_unit = 'share' AND amount / (volume * 1.0)   NOT BETWEEN low*0.98 AND high*1.02))"
            % (table, where_stock, verifiable_sql),
            args + list(SUPPORTED_UNITS)).fetchone()[0]

    detail = ("stock_rows=%d verifiable=%d contradicted=%d quarantined=%d "
              "benchmarks_excluded=%d" % (total, verifiable, contradicted, quarantined,
                                          len(marks)))
    if contradicted:
        return FAIL, contradicted, detail
    if quarantined:
        # Missing unit evidence. Never PASS.
        return UNKNOWN, quarantined, detail + (
            "; quarantined rows lack a supported declared unit or a common price basis")
    return PASS, 0, detail


def chk_provenance(conn, table="daily_bars"):
    """D5 referential validity of run ids, not merely NOT NULL."""
    guard = _empty_guard(conn, table)
    if guard:
        return guard
    if not _readable(conn, "ingest_runs"):
        return UNKNOWN, None, "ingest_runs absent; provenance cannot be resolved"
    nulls = conn.execute(
        "SELECT COUNT(*) FROM %s WHERE ingest_run_id IS NULL" % table).fetchone()[0]
    dangling = conn.execute(
        "SELECT COUNT(*) FROM %s d LEFT JOIN ingest_runs r ON r.id = d.ingest_run_id "
        "WHERE d.ingest_run_id IS NOT NULL AND r.id IS NULL" % table).fetchone()[0]
    total = nulls + dangling
    return (PASS if total == 0 else FAIL), total, "null=%d dangling=%d" % (nulls, dangling)


def chk_duplicates(conn, table="daily_bar_cache", keys=("symbol", "trade_date")):
    """D7 duplicate business keys (restored; the rewritten registry had dropped it)."""
    guard = _empty_guard(conn, table)
    if guard:
        return guard
    cols = ", ".join(keys)
    n = conn.execute(
        "SELECT COUNT(*) FROM (SELECT %s, COUNT(*) c FROM %s GROUP BY %s HAVING c > 1)"
        % (cols, table, cols)).fetchone()[0]
    return (PASS if n == 0 else FAIL), n, "duplicate key groups on (%s)" % cols


def chk_population(conn, expected_symbols=None, expected_sessions=None,
                   table="daily_bar_cache"):
    """D0 the batch actually contains what it claims to contain.

    Without this, a nearly-empty staging database passes every row-level check simply by
    having almost nothing to violate.
    """
    guard = _empty_guard(conn, table)
    if guard:
        return guard
    syms = conn.execute("SELECT COUNT(DISTINCT symbol) FROM %s" % table).fetchone()[0]
    sess = conn.execute("SELECT COUNT(DISTINCT trade_date) FROM %s" % table).fetchone()[0]
    if expected_symbols is None and expected_sessions is None:
        return UNKNOWN, (syms, sess), (
            "no expected population declared; observed symbols=%d sessions=%d" % (syms, sess))
    problems = []
    if expected_symbols is not None and syms != expected_symbols:
        problems.append("symbols %d != expected %d" % (syms, expected_symbols))
    if expected_sessions is not None and sess < expected_sessions:
        problems.append("sessions %d < expected %d" % (sess, expected_sessions))
    return (PASS if not problems else FAIL), (syms, sess), (
        "; ".join(problems) or "symbols=%d sessions=%d" % (syms, sess))


def chk_cross_store(conn, left="daily_bar_cache", right="daily_bars",
                    declared_transformation=None, tolerance=0.005):
    """D8 reconcile two views that claim the same source, basis and vintage.

    If no transformation is declared, the two series are NOT assumed comparable. Demanding
    raw price equality between a raw view and an adjusted one would manufacture a failure;
    silently comparing them would manufacture a pass. Both are refused.
    """
    for table in (left, right):
        guard = _empty_guard(conn, table)
        if guard:
            return guard
    if declared_transformation is None:
        return UNKNOWN, None, (
            "no declared transformation between %s and %s; raw-vs-adjusted comparison "
            "refused rather than assumed" % (left, right))
    if declared_transformation != "identity":
        return UNKNOWN, None, (
            "transformation %r not implemented in this gate" % declared_transformation)
    common = conn.execute(
        "SELECT COUNT(*) FROM %s l JOIN %s r ON r.symbol = l.symbol "
        "AND r.trade_date = l.trade_date" % (left, right)).fetchone()[0]
    if common == 0:
        return UNKNOWN, 0, "no common keys between %s and %s" % (left, right)
    differing = conn.execute(
        "SELECT COUNT(*) FROM %s l JOIN %s r ON r.symbol = l.symbol "
        "AND r.trade_date = l.trade_date "
        "WHERE l.close IS NULL OR r.close IS NULL OR ABS(l.close - r.close) > ?"
        % (left, right), (tolerance,)).fetchone()[0]
    return (PASS if differing == 0 else FAIL), differing, (
        "identity transformation; common=%d differing=%d tolerance=%s"
        % (common, differing, tolerance))


# ------------------------------------------------------------------- archive integrity

def _schema_fingerprint(conn):
    rows = conn.execute(
        "SELECT type, name, tbl_name, sql FROM sqlite_master ORDER BY type, name").fetchall()
    h = hashlib.sha256()
    for row in rows:
        h.update(("|".join("" if v is None else str(v) for v in row) + "\n").encode())
    return h.hexdigest()


def archive_fingerprint(conn, full=True):
    """Content hash over the WHOLE database when full=True.

    D6 previously hashed only symbol/date/adjustment/close/volume/amount, so editing an
    archive's open price or provider left the digest unchanged. A vintage is the entire
    database - schema, every table, every column - so that is what is hashed.

    full=False keeps the narrow legacy digest for the original regression cases.
    """
    if not full:
        h = hashlib.sha256()
        for row in conn.execute(
            "SELECT symbol, trade_date, adjustment_mode, close, volume, amount "
            "FROM daily_bars ORDER BY symbol, trade_date, adjustment_mode"
        ):
            h.update(("|".join("" if v is None else str(v) for v in row) + "\n").encode())
        return h.hexdigest()

    h = hashlib.sha256()
    h.update(("schema:" + _schema_fingerprint(conn) + "\n").encode())
    tables = [r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' "
        "ORDER BY name")]
    for table in tables:
        cols = [r[1] for r in conn.execute("PRAGMA table_info(%s)" % table)]
        if not cols:
            continue
        projection = ", ".join('"%s"' % c for c in cols)
        h.update(("table:%s(%s)\n" % (table, ",".join(cols))).encode())
        for row in conn.execute(
            "SELECT %s FROM %s ORDER BY %s" % (projection, table, projection)
        ):
            h.update(("|".join("" if v is None else str(v) for v in row) + "\n").encode())
    return h.hexdigest()


def chk_archive(conn, baseline=None, full=True):
    """D6 archive preservation by whole-database fingerprint."""
    if not _readable(conn, "daily_bars") and not full:
        return UNKNOWN, None, "daily_bars absent"
    fp = archive_fingerprint(conn, full=full)
    if baseline is None:
        return UNKNOWN, fp, "no frozen baseline supplied; fingerprint recorded only"
    return (PASS if fp == baseline else FAIL), fp, (
        "baseline=%s..%s observed=%s..%s" % (baseline[:8], baseline[-4:], fp[:8], fp[-4:]))


# --------------------------------------------------------------- production diagnostic

def production_run():
    """Read-only diagnostic over production. NOT a validation gate - see staging_gate.py."""
    t, h = ro(TRADING), ro(HISTORY)
    both = sqlite3.connect("file::memory:", uri=True)
    both.row_factory = sqlite3.Row
    both.execute("ATTACH ? AS tl", ("file:%s?mode=ro" % TRADING,))
    both.execute("ATTACH ? AS mh", ("file:%s?mode=ro" % HISTORY,))
    both.execute("CREATE TEMP VIEW daily_bar_cache AS SELECT * FROM tl.daily_bar_cache")
    both.execute("CREATE TEMP VIEW instruments AS SELECT * FROM mh.instruments")
    both.execute("CREATE TEMP VIEW daily_bars AS SELECT * FROM mh.daily_bars")

    results = [
        ("D0", "expected population declared", chk_population(both)),
        ("D1", "impossible / non-session dates", chk_dates(t)),
        ("D2", "symbol namespace and catalog (benchmarks routed)",
         chk_symbols(both, benchmarks=BENCHMARKS)),
        ("D3", "missing / nonpositive / OHLC-violating prices", chk_prices(t)),
        ("D4", "stock volume units verified, remainder quarantined",
         chk_units(t, benchmarks=BENCHMARKS)),
        ("D5", "ingest-run provenance referentially valid", chk_provenance(h)),
        ("D6", "archive whole-database fingerprint", chk_archive(h, None, full=True)),
        ("D7", "duplicate business keys", chk_duplicates(t)),
        ("D8", "cross-store same-basis reconciliation", chk_cross_store(both)),
    ]
    for c in (t, h, both):
        c.close()
    return [{"id": i, "description": d, "status": r[0], "observed": r[1], "detail": r[2]}
            for i, d, r in results]


if __name__ == "__main__":
    rows = production_run()
    width = max(len(r["description"]) for r in rows)
    print("production diagnostic (read-only, NOT a validation gate) calendar %s"
          % CALENDAR_SHA256[:12])
    for r in rows:
        print("  %-3s %-*s %-14s observed=%s" % (
            r["id"], width, r["description"], r["status"], r["observed"]))
        print("      %s" % r["detail"])
    counts = {}
    for r in rows:
        counts[r["status"]] = counts.get(r["status"], 0) + 1
    print("  summary: %s" % counts)
    print("  NOTE: this mode reports observations and always exits 0. The pass/fail gate "
          "is staging_gate.py validate.")
