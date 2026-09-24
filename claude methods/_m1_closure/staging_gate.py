"""G1-G3 - the executable staging gate: per-key identity, verified representation, path-safe.

  snapshot   read original archives, write a frozen baseline. The ONLY writing mode.
  validate   read staging + archives + manifest + calendar + frozen baseline, decide.
             Opens everything mode=ro and never writes anything, anywhere.

Exit codes
----------
  0  every required gate is PASS or NOT_APPLICABLE
  1  at least one required gate is FAIL or UNKNOWN
  2  usage/input/path-role/configuration error, raised BEFORE any write

UNKNOWN is a failing outcome here. A diagnostic may report "we do not know"; a gate that
authorizes a download may not.

The grain
---------
The contract is a (security, session, basis) RECORD in each consumed view. Marginal
counts are not evidence about that grain: the acceptance review deleted one history
record and replaced an entire 728-row series with an unknown symbol, and both passed
because distinct symbol and session counts were unchanged and the reconciliation used an
inner join that silently dropped non-matching keys. Expected keys are therefore derived
from the MANIFEST, never from what the data happens to contain, and both directions
(missing and unexpected) are reported.

What each closure round fixed
-----------------------------
G1a  H0 compared only distinct symbol/session counts and X2 inner-joined, so a missing or
     substituted history series passed. Membership and per-security eligible-key coverage
     are now validated in BOTH views against the manifest, with missing-in-left and
     missing-in-right reported separately.
G1b  X1 trusted the --pricing-basis/--history-basis ARGUMENTS. Stored adjustment_mode is
     now read from each view and must agree with the declared basis, with mixed bases
     rejected. Identity reconciliation compares the declared field list (OHLC + close) at
     an explicit tolerance, not close alone.
G2a  The delivered manifest leaves list_date blank for the two index benchmarks, so the
     stock listing rule made complete benchmark data UNRESOLVED. Benchmarks now have
     their own eligibility contract over the research window; no IPO date is invented and
     neither index is removed.
G2b  --warmup-required --warmup-sessions N without --warmup-start silently became
     advisory NOT_APPLICABLE. Incomplete required configuration is now an input error, or
     the interval is derived from the pinned calendar. Feature readiness is reported
     separately from price coverage.
G3   --baseline-out was never checked against inputs and could overwrite an archive under
     --force. All roles are resolved and validated before any write.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import os
import sqlite3
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from acceptance_runner import (  # noqa: E402
    FAIL, NOT_APPLICABLE, PASS, SUCCESSFUL, UNKNOWN, archive_fingerprint, chk_dates,
    chk_duplicates, chk_prices, chk_provenance, chk_symbols, chk_units,
)

RESEARCH_START, RESEARCH_END = "2023-09-04", "2026-09-04"
SUPPORTED_TRANSFORMATIONS = ("identity",)
IDENTITY_FIELDS = ("open", "high", "low", "close")


class SystemExit2(Exception):
    """Usage / input / path-role / configuration error -> exit 2."""


# ------------------------------------------------------------------ G3 path safety

def _resolve(path) -> Path:
    return Path(path).expanduser().resolve()


def _alias(a: Path, b: Path) -> bool:
    if a == b:
        return True
    if os.name == "nt" and str(a).casefold() == str(b).casefold():
        return True
    try:
        if a.exists() and b.exists() and os.path.samefile(a, b):
            return True
    except OSError:
        pass
    return False


def guard_paths(*, output=None, protected=(), distinct=()):
    for role_a, path_a, role_b, path_b in distinct:
        if _alias(path_a, path_b):
            raise SystemExit2("path role collision: --%s and --%s both resolve to %s"
                              % (role_a, role_b, path_a))
    if output is None:
        return
    for role, path in protected:
        if _alias(output, path):
            raise SystemExit2(
                "refusing to write baseline output over a protected input: "
                "--baseline-out resolves to the same file as --%s (%s). "
                "--force does not override this." % (role, path))


def ro(path: Path) -> sqlite3.Connection:
    if not Path(path).exists():
        raise SystemExit2("database not found: %s" % path)
    conn = sqlite3.connect("file:%s?mode=ro" % path, uri=True)
    conn.execute("PRAGMA query_only=1")
    conn.row_factory = sqlite3.Row
    return conn


def load_calendar(path: Path):
    raw = Path(path).read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    data = json.loads(raw.decode("utf-8"))
    values = [str(x["trade_date"] if isinstance(x, dict) else x) for x in data]
    sessions = sorted({
        (v[:4] + "-" + v[4:6] + "-" + v[6:8]) if len(v) == 8 and v.isdigit() else v
        for v in values})
    return sessions, digest


def load_manifest(path: Path):
    """Keep listing metadata, and label each row's eligibility contract (G2a).

    A benchmark is not a late IPO: the delivered manifest leaves list_date blank for
    SH000300/SH000001, and applying the stock listing rule to them made complete data
    UNRESOLVED. Benchmarks get their own contract instead of an invented IPO date.
    """
    with io.open(path, encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    stocks, benchmarks = [], []
    for r in rows:
        is_benchmark = r.get("stratum") == "benchmark"
        entry = {
            "symbol": r["symbol"],
            "list_date": (r.get("list_date") or "").strip(),
            "delist_date": (r.get("delist_date") or "").strip(),
            "stratum": r.get("stratum", ""),
            "eligibility_contract": ("benchmark_research_window" if is_benchmark
                                     else "stock_listing_interval"),
        }
        (benchmarks if is_benchmark else stocks).append(entry)
    return stocks, benchmarks


# ----------------------------------------------------------------- G2a eligibility

def entry_eligibility(entry, window):
    """Eligible sessions for one manifest row, by its declared contract.

    stock_listing_interval    : [max(list_date, start) .. min(delist_date, end)];
                                a blank list_date is UNRESOLVED, never "complete".
    benchmark_research_window : the whole research window. An index has no IPO; a
                                list_date, if present, is honoured as a lower bound.
    """
    lo, hi = window[0], window[-1]
    if entry["eligibility_contract"] == "benchmark_research_window":
        if entry["list_date"]:
            lo = max(lo, entry["list_date"])
        if entry["delist_date"]:
            hi = min(hi, entry["delist_date"])
        return [s for s in window if lo <= s <= hi], "benchmark_research_window"
    if not entry["list_date"]:
        return [], "unknown_list_date"
    lo = max(lo, entry["list_date"])
    if entry["delist_date"]:
        hi = min(hi, entry["delist_date"])
    if lo > hi:
        return [], "listed_after_interval"
    return [s for s in window if lo <= s <= hi], "stock_listing_interval"


def expected_key_map(entries, window):
    """symbol -> set(eligible sessions), derived from the MANIFEST only (G1a).

    A KNOWN-EMPTY eligible set is kept in `expected` as an empty set, not dropped. It
    was previously moved aside and skipped, which inverted the outcome: a correctly
    empty series was reported "absent" and FAILED, while injecting one ineligible record
    made the symbol appear, skipped the key comparison, and PASSED. Adding invalid data
    must never turn a failure into a success.

    Known-empty (the security is entirely outside this interval) is reported separately
    from UNKNOWN (eligibility cannot be determined at all); the two must not be conflated.
    """
    expected, unresolved, known_empty = {}, [], []
    for entry in entries:
        elig, basis = entry_eligibility(entry, window)
        if basis == "unknown_list_date":
            unresolved.append(entry["symbol"])
            continue
        expected[entry["symbol"]] = set(elig)   # may legitimately be empty - KEPT
        if not elig:
            known_empty.append(entry["symbol"])
    return expected, unresolved, known_empty


def observed_key_map(conn, table, symbols, lo, hi):
    seen = {}
    for sym in symbols:
        seen[sym] = {r[0] for r in conn.execute(
            "SELECT DISTINCT trade_date FROM %s WHERE symbol = ? "
            "AND trade_date BETWEEN ? AND ?" % table, (sym, lo, hi))}
    return seen


def membership_gate(conn, table, entries, window, label, view_declared=None,
                    empty_domain="reject"):
    """G1a - per-security identity AND eligible-key completeness, both directions.

    Counting distinct symbols and sessions cannot see a deleted record or a substituted
    series; this compares the actual key sets against the manifest contract.

    `entries` is the sub-population being measured (stocks, or benchmarks).
    `view_declared` is every symbol the VIEW is allowed to contain, which is what an
    unexpected symbol is judged against - otherwise checking the stocks would flag the
    benchmarks sharing the same table, and vice versa.
    `empty_domain` decides what a KNOWN-EMPTY eligible set means for this interval:
        "reject" - the batch contract forbids a member with no eligible sessions here.
                   Used for the research interval: a pilot member that can contribute no
                   eligible research record is a manifest error, and it is rejected on
                   the manifest, independently of what the data contains.
        "allow"  - legitimately empty. Used for warm-up: a security listed after the
                   warm-up interval simply has no warm-up records to supply. Feature
                   depth is judged separately by the readiness gate.
    Under BOTH settings an observed record inside an empty domain is a failure.
    """
    expected, unresolved, known_empty = expected_key_map(entries, window)
    if not expected and not unresolved:
        return UNKNOWN, None, "%s: manifest declares no members" % label

    observed_symbols = {r[0] for r in conn.execute(
        "SELECT DISTINCT symbol FROM %s WHERE trade_date BETWEEN ? AND ?"
        % table, (window[0], window[-1]))}
    declared = {e["symbol"] for e in entries}
    allowed = set(view_declared) if view_declared is not None else declared
    unexpected = sorted(observed_symbols - allowed)
    # A security whose eligible domain is known-empty is CORRECTLY absent from the data;
    # only a symbol that owes eligible records can be "absent".
    owes_records = {sym for sym, want in expected.items() if want}
    absent = sorted(owes_records - observed_symbols)

    seen = observed_key_map(conn, table, sorted(expected), window[0], window[-1])
    missing_keys, extra_keys, complete = [], [], 0
    for sym, want in expected.items():
        got = seen.get(sym, set())
        gap = want - got
        # K1: the other direction. A record inside the declared interval that is NOT an
        # eligible session - a pre-listing or post-delisting row - is just as much a
        # contract violation as a missing one, and two copies agreeing about it proves
        # nothing about eligibility. Only keys WITHIN this gate's interval are judged,
        # so a legitimate declared warm-up record is never mistaken for an unexpected
        # research record.
        extra = got - want
        if gap:
            missing_keys.append((sym, len(gap), sorted(gap)[:2]))
        if extra:
            extra_keys.append((sym, len(extra), sorted(extra)[:2]))
        if not gap and not extra:
            complete += 1

    correctly_empty = [sym for sym in known_empty if not seen.get(sym)]
    forbidden_empty = sorted(known_empty) if empty_domain == "reject" else []

    detail = ("%s: declared=%d complete=%d missing_series=%d unexpected_keys=%d "
              "unexpected_symbols=%d absent_symbols=%d unresolved=%d "
              "known_empty=%d correctly_empty=%d empty_domain=%s"
              % (label, len(declared), complete, len(missing_keys), len(extra_keys),
                 len(unexpected), len(absent), len(unresolved), len(known_empty),
                 len(correctly_empty), empty_domain))
    if unexpected:
        detail += "; unexpected_symbols=%s" % unexpected[:5]
    if absent:
        detail += "; absent=%s" % absent[:5]
    if missing_keys:
        detail += "; missing=%s" % missing_keys[:3]
    if extra_keys:
        detail += "; ineligible_records=%s" % extra_keys[:3]
    if unresolved:
        detail += "; unresolved=%s" % unresolved[:5]
    if forbidden_empty:
        detail += ("; MANIFEST REJECTED - members with no eligible session in this "
                   "interval are forbidden by the batch contract: %s"
                   % forbidden_empty[:5])

    if unexpected or absent or missing_keys or extra_keys or forbidden_empty:
        return FAIL, complete, detail
    if unresolved:
        return UNKNOWN, complete, detail
    return PASS, complete, detail


# ------------------------------------------------------ G1b representation & identity

def basis_gate(conn, table, declared, label):
    """G1b - the STORED adjustment_mode must match what the caller declared."""
    rows = conn.execute(
        "SELECT adjustment_mode, COUNT(*) FROM %s GROUP BY adjustment_mode" % table
    ).fetchall()
    if not rows:
        return UNKNOWN, None, "%s: no rows to inspect" % label
    modes = {("" if r[0] is None else str(r[0])): r[1] for r in rows}
    if len(modes) > 1:
        return FAIL, sorted(modes), ("%s: mixed adjustment bases stored %s; a single "
                                     "declared basis cannot describe this view"
                                     % (label, modes))
    stored = next(iter(modes))
    if not stored.strip():
        return UNKNOWN, stored, "%s: stored adjustment_mode is blank/NULL" % label
    if stored != declared:
        return FAIL, stored, ("%s: stored basis %r disagrees with declared %r"
                              % (label, stored, declared))
    return PASS, stored, "%s: stored basis %r matches the declaration" % (label, stored)


def identity_gate(conn, left, right, fields, tolerance, window):
    """G1b/G1a - compare the fields identity actually promises, over the full key union.

    An inner join hides missing keys, and comparing close alone hides a changed high.
    Both are checked here.
    """
    lkeys = {(r[0], r[1]) for r in conn.execute(
        "SELECT symbol, trade_date FROM %s WHERE trade_date BETWEEN ? AND ?"
        % left, (window[0], window[-1]))}
    rkeys = {(r[0], r[1]) for r in conn.execute(
        "SELECT symbol, trade_date FROM %s WHERE trade_date BETWEEN ? AND ?"
        % right, (window[0], window[-1]))}
    only_left, only_right = lkeys - rkeys, rkeys - lkeys

    predicate = " OR ".join(
        "l.%s IS NULL OR r.%s IS NULL OR ABS(l.%s - r.%s) > ?" % (f, f, f, f)
        for f in fields)
    mismatch = conn.execute(
        "SELECT COUNT(*) FROM %s l JOIN %s r ON r.symbol = l.symbol "
        "AND r.trade_date = l.trade_date WHERE l.trade_date BETWEEN ? AND ? AND (%s)"
        % (left, right, predicate),
        (window[0], window[-1]) + tuple([tolerance] * len(fields))).fetchone()[0]

    detail = ("fields=%s tol=%s common=%d only_in_%s=%d only_in_%s=%d mismatched=%d"
              % (",".join(fields), tolerance, len(lkeys & rkeys), left, len(only_left),
                 right, len(only_right), mismatch))
    if only_left or only_right:
        detail += "; sample_only_left=%s sample_only_right=%s" % (
            sorted(only_left)[:2], sorted(only_right)[:2])
    if only_left or only_right or mismatch:
        return FAIL, mismatch, detail
    return PASS, 0, detail


# --------------------------------------------------------------------------- snapshot

def cmd_snapshot(args) -> int:
    arch_t = _resolve(args.archive_trading)
    arch_h = _resolve(args.archive_history)
    calendar = _resolve(args.calendar)
    out = _resolve(args.baseline_out)

    guard_paths(output=out,
                protected=[("archive-trading", arch_t), ("archive-history", arch_h),
                           ("calendar", calendar)],
                distinct=[("archive-trading", arch_t, "archive-history", arch_h)])

    _, calendar_sha = load_calendar(calendar)
    baseline = {"kind": "frozen_archive_baseline", "archives": {},
                "calendar_sha256": calendar_sha, "calendar_path": str(calendar)}
    for name, path in (("trading", arch_t), ("history", arch_h)):
        conn = ro(path)
        baseline["archives"][name] = {
            "path": str(path),
            "file_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "content_fingerprint": archive_fingerprint(conn, full=True),
            "bytes": path.stat().st_size,
        }
        conn.close()

    if out.exists() and not args.force:
        raise SystemExit2("baseline already exists: %s (pass --force to replace)" % out)
    if out.exists() and args.force:
        try:
            if json.loads(out.read_text(encoding="utf-8")).get("kind") != "frozen_archive_baseline":
                raise ValueError
        except (ValueError, OSError, UnicodeDecodeError):
            raise SystemExit2("--force refuses to replace %s: it is not a "
                              "frozen_archive_baseline document" % out) from None

    out.write_text(json.dumps(baseline, indent=2, ensure_ascii=False), encoding="utf-8")
    print("snapshot written: %s" % out)
    for name, info in baseline["archives"].items():
        print("  %-8s %s" % (name, info["path"]))
        print("           file=%s content=%s"
              % (info["file_sha256"][:16], info["content_fingerprint"][:16]))
    return 0


# --------------------------------------------------------------------------- validate

def resolve_warmup(args, sessions):
    """G2b - a required warm-up may never be silently downgraded to advisory.

    Returns (interval, required). Incomplete required configuration is an input error.
    """
    before = [s for s in sessions if s < RESEARCH_START]
    wants_warmup = bool(args.warmup_start or args.warmup_required or args.warmup_sessions)
    if wants_warmup and not args.warmup_consumers:
        # K2: readiness is meaningless without saying which view feeds the features.
        raise SystemExit2(
            "--warmup-consumers must be declared (pricing|history|both) whenever a "
            "warm-up is requested; an unpinned consumer boundary would let a "
            "pricing-only count be read as history or both-view readiness")
    if args.warmup_start:
        warm = [s for s in before if s >= args.warmup_start]
        if not warm:
            raise SystemExit2("--warmup-start %s yields no sessions strictly before %s"
                              % (args.warmup_start, RESEARCH_START))
        return warm, args.warmup_required
    if args.warmup_required or args.warmup_sessions:
        if not args.warmup_sessions:
            raise SystemExit2(
                "--warmup-required needs either --warmup-start or --warmup-sessions; "
                "an incomplete required warm-up configuration must not fall back to "
                "advisory")
        # Derive the interval explicitly from the pinned calendar.
        if len(before) < args.warmup_sessions:
            raise SystemExit2("calendar holds only %d sessions before %s; cannot derive a "
                              "%d-session warm-up" % (len(before), RESEARCH_START,
                                                      args.warmup_sessions))
        return before[-args.warmup_sessions:], args.warmup_required
    return None, False


def cmd_validate(args) -> int:
    used = []

    def track(p):
        rp = _resolve(p)
        used.append(str(rp))
        return rp

    baseline_path = track(args.baseline)
    calendar_path = track(args.calendar)
    manifest_path = track(args.pilot_manifest)
    stag_t = track(args.staging_trading)
    stag_h = track(args.staging_history)
    arch_t = track(args.archive_trading)
    arch_h = track(args.archive_history)

    guard_paths(distinct=[
        ("staging-trading", stag_t, "archive-trading", arch_t),
        ("staging-history", stag_h, "archive-history", arch_h),
        ("staging-trading", stag_t, "staging-history", stag_h)])

    if not baseline_path.exists():
        raise SystemExit2("frozen baseline not found: %s" % baseline_path)
    baseline_before = hashlib.sha256(baseline_path.read_bytes()).hexdigest()
    baseline = json.loads(baseline_path.read_text(encoding="utf-8"))

    sessions, calendar_sha = load_calendar(calendar_path)
    stocks, benchmarks = load_manifest(manifest_path)
    mark_syms = [e["symbol"] for e in benchmarks]
    window = [s for s in sessions if RESEARCH_START <= s <= RESEARCH_END]
    warm_interval, warm_required = resolve_warmup(args, sessions)

    # History scope is DECLARED, never inferred from what the data contains.
    history_entries = stocks if args.history_scope == "stocks" else stocks + benchmarks

    conn = sqlite3.connect("file::memory:", uri=True)
    conn.row_factory = sqlite3.Row
    for path in (stag_t, stag_h):
        if not path.exists():
            raise SystemExit2("database not found: %s" % path)
    conn.execute("ATTACH ? AS sp", ("file:%s?mode=ro" % stag_t,))
    conn.execute("ATTACH ? AS sh", ("file:%s?mode=ro" % stag_h,))
    conn.execute("CREATE TEMP VIEW daily_bar_cache AS SELECT * FROM sp.daily_bar_cache")
    conn.execute("CREATE TEMP VIEW instruments AS SELECT * FROM sp.instruments")
    conn.execute("CREATE TEMP VIEW daily_bars AS SELECT * FROM sh.daily_bars")
    conn.execute("CREATE TEMP VIEW ingest_runs AS SELECT * FROM sh.ingest_runs")

    results = []

    def add(cid, desc, outcome, required=True):
        status, observed, detail = outcome
        results.append({"id": cid, "description": desc, "status": status,
                        "observed": observed, "detail": detail, "required": required})

    add("C0", "pinned calendar matches the frozen baseline",
        (PASS, calendar_sha[:16], "sha256 %s" % calendar_sha[:16])
        if calendar_sha == baseline.get("calendar_sha256")
        else (FAIL, calendar_sha[:16], "calendar sha %s != baseline %s"
              % (calendar_sha[:16], str(baseline.get("calendar_sha256"))[:16])))

    for name, path in (("trading", arch_t), ("history", arch_h)):
        recorded = baseline.get("archives", {}).get(name)
        if not recorded:
            add("A_%s" % name, "archive %s present in baseline" % name,
                (UNKNOWN, None, "baseline has no record for %s" % name))
            continue
        if not path.exists():
            add("A_%s" % name, "archive %s readable" % name, (FAIL, None, "missing: %s" % path))
            continue
        file_sha = hashlib.sha256(path.read_bytes()).hexdigest()
        ac = ro(path)
        content = archive_fingerprint(ac, full=True)
        ac.close()
        ok = (file_sha == recorded["file_sha256"]
              and content == recorded["content_fingerprint"])
        add("A_%s" % name, "archive %s unchanged (file + whole-db content)" % name,
            (PASS if ok else FAIL, content[:16],
             "file_match=%s content_match=%s"
             % (file_sha == recorded["file_sha256"],
                content == recorded["content_fingerprint"])))

    # --- pricing view ---
    add("P1", "pricing dates are real sessions", chk_dates(conn, table="daily_bar_cache"))
    add("P2", "pricing symbols (benchmarks routed)",
        chk_symbols(conn, benchmarks=mark_syms, table="daily_bar_cache"))
    add("P3", "pricing OHLC / positivity", chk_prices(conn, table="daily_bar_cache"))
    add("P4", "stock volume units from raw-basis evidence",
        chk_units(conn, benchmarks=mark_syms, table="daily_bar_cache"))
    add("P5", "pricing duplicate business keys",
        chk_duplicates(conn, table="daily_bar_cache", keys=("symbol", "trade_date")))
    add("P6", "pricing stored basis matches the declaration",
        basis_gate(conn, "daily_bar_cache", args.pricing_basis, "pricing"))

    # --- G1a per-key membership in BOTH views, from the manifest ---
    pricing_declared = [e["symbol"] for e in stocks + benchmarks]
    history_declared = [e["symbol"] for e in history_entries]
    add("M1", "pricing membership + eligible-key completeness (stocks)",
        membership_gate(conn, "daily_bar_cache", stocks, window, "pricing/stocks",
                        view_declared=pricing_declared))
    add("M2", "pricing membership + eligible-key completeness (benchmarks)",
        membership_gate(conn, "daily_bar_cache", benchmarks, window, "pricing/benchmarks",
                        view_declared=pricing_declared))
    add("M3", "history membership + eligible-key completeness (declared scope %s)"
        % args.history_scope,
        membership_gate(conn, "daily_bars", history_entries, window,
                        "history/%s" % args.history_scope,
                        view_declared=history_declared))

    # --- history view ---
    add("H1", "history dates are real sessions", chk_dates(conn, table="daily_bars"))
    add("H2", "history OHLC / positivity", chk_prices(conn, table="daily_bars"))
    add("H3", "history duplicate business keys",
        chk_duplicates(conn, table="daily_bars",
                       keys=("symbol", "trade_date", "adjustment_mode")))
    add("H4", "history ingest-run provenance referentially valid",
        chk_provenance(conn, table="daily_bars"))
    add("H5", "history stored basis matches the declaration",
        basis_gate(conn, "daily_bars", args.history_basis, "history"))

    # --- G1b declared reconciliation over the promised fields ---
    if args.transformation is None:
        add("X1", "declared cross-view transformation",
            (UNKNOWN, None, "no --transformation declared; the two views cannot be "
                            "reconciled and raw/adjusted equality must not be assumed"))
    elif args.transformation not in SUPPORTED_TRANSFORMATIONS:
        add("X1", "declared cross-view transformation",
            (UNKNOWN, args.transformation,
             "transformation %r is unsupported; required evidence is unavailable, so "
             "acceptance is blocked rather than skipped" % args.transformation))
    elif args.pricing_basis != args.history_basis:
        add("X1", "declared cross-view transformation",
            (FAIL, args.transformation,
             "identity declared but bases differ (pricing=%s history=%s); raw and "
             "adjusted prices must not be compared as if identical"
             % (args.pricing_basis, args.history_basis)))
    else:
        add("X1", "declared cross-view transformation",
            (PASS, args.transformation,
             "identity on a common '%s' basis (stored values verified by P6/H5)"
             % args.pricing_basis))
        add("X2", "identity reconciliation over %s" % ",".join(IDENTITY_FIELDS),
            identity_gate(conn, "daily_bar_cache", "daily_bars", IDENTITY_FIELDS,
                          args.identity_tolerance, window))

    # --- G2b warm-up: price coverage vs feature readiness, kept apart ---
    if warm_interval:
        overlap = [s for s in warm_interval if s >= RESEARCH_START]
        add("V3a", "warm-up interval does not overlap the research window",
            (PASS if not overlap else FAIL, len(warm_interval),
             "warm-up %s..%s (%d sessions), research starts %s, overlap=%d"
             % (warm_interval[0], warm_interval[-1], len(warm_interval),
                RESEARCH_START, len(overlap))))

        # K2: the DECLARED feature-warm-up consumers. Every required consumer view is
        # validated for eligibility and completeness over the warm-up interval, and a
        # view that is not consumed is reported as such rather than silently certified.
        consumer_map = {
            "pricing": [("daily_bar_cache", "pricing", stocks + benchmarks, pricing_declared)],
            "history": [("daily_bars", "history", history_entries, history_declared)],
            "both": [("daily_bar_cache", "pricing", stocks + benchmarks, pricing_declared),
                     ("daily_bars", "history", history_entries, history_declared)],
        }
        consumers = consumer_map[args.warmup_consumers]
        consumed_tables = [t for t, _, _, _ in consumers]

        for table, name, entries, allowed in consumers:
            add("W1_%s" % name,
                "warm-up membership + eligible-key completeness (%s, consumed)" % name,
                membership_gate(conn, table, entries, warm_interval,
                                "warmup/%s" % name, view_declared=allowed,
                                empty_domain="allow"),
                required=warm_required)

        for table, name in (("daily_bar_cache", "pricing"), ("daily_bars", "history")):
            if table not in consumed_tables:
                add("W0_%s" % name, "%s warm-up declared NOT CONSUMED by features" % name,
                    (NOT_APPLICABLE, None,
                     "--warmup-consumers=%s; this view supplies no feature warm-up, so "
                     "its warm-up is neither validated nor certified here. Readiness "
                     "below is scoped to %s only and must not be read as %s readiness."
                     % (args.warmup_consumers, args.warmup_consumers, name)),
                    required=False)

        identity_ok = (args.transformation in SUPPORTED_TRANSFORMATIONS
                       and args.pricing_basis == args.history_basis)
        if args.warmup_consumers == "both" and identity_ok:
            add("W2", "warm-up identity reconciliation over %s" % ",".join(IDENTITY_FIELDS),
                identity_gate(conn, "daily_bar_cache", "daily_bars", IDENTITY_FIELDS,
                              args.identity_tolerance, warm_interval),
                required=warm_required)

        depth = args.warmup_sessions or len(warm_interval)
        short, ready = [], 0
        for entry in stocks:
            elig, _ = entry_eligibility(entry, warm_interval)
            worst = None
            for table, name, _, _ in consumers:
                seen = {r[0] for r in conn.execute(
                    "SELECT DISTINCT trade_date FROM %s WHERE symbol = ? "
                    "AND trade_date BETWEEN ? AND ?" % table,
                    (entry["symbol"], warm_interval[0], warm_interval[-1]))}
                # Count only ELIGIBLE observations; dates before listing are not evidence.
                usable = len(set(elig) & seen)
                if worst is None or usable < worst[1]:
                    worst = (name, usable)
            if worst[1] >= depth:
                ready += 1
            else:
                short.append((entry["symbol"], worst[1], worst[0], len(elig)))
        add("V3b", "per-security feature readiness in %s (>= %d eligible observations)"
            % (args.warmup_consumers, depth),
            (PASS if not short else FAIL, ready,
             "scope=%s ready=%d short=%d depth=%d; short sample=%s. This counts ELIGIBLE "
             "warm-up observations in the declared consumer view(s) only. Complete "
             "eligible price coverage is gate M1: a new listing can satisfy M1 in full "
             "and still be short here, and that is reported rather than waived."
             % (args.warmup_consumers, ready, len(short), depth,
                sorted(short, key=lambda x: x[1])[:3])),
            required=warm_required)
    else:
        add("V3", "warm-up coverage",
            (NOT_APPLICABLE, None,
             "no warm-up requested; no feature-readiness claim is made for any view"),
            required=False)

    conn.close()

    baseline_after = hashlib.sha256(baseline_path.read_bytes()).hexdigest()
    add("B0", "frozen baseline unmodified by validation",
        (PASS if baseline_after == baseline_before else FAIL, baseline_after[:16],
         "before=%s after=%s" % (baseline_before[:16], baseline_after[:16])))

    width = max(len(r["description"]) for r in results)
    print("staging validation")
    for p in used:
        print("  input: %s" % p)
    print()
    for r in results:
        flag = "" if r["required"] else "  (advisory)"
        print("  %-10s %-*s %-14s%s" % (r["id"], width, r["description"], r["status"], flag))
        print("             %s" % r["detail"])

    blocking = [r for r in results if r["required"] and r["status"] not in SUCCESSFUL]
    counts = {}
    for r in results:
        counts[r["status"]] = counts.get(r["status"], 0) + 1
    print("\n  summary: %s" % counts)
    if blocking:
        print("  RESULT: FAILED - %d required gate(s) not satisfied: %s"
              % (len(blocking), ", ".join(r["id"] for r in blocking)))
        return 1
    print("  RESULT: SUCCEEDED - all required gates PASS/NOT_APPLICABLE")
    return 0


def build_parser():
    p = argparse.ArgumentParser(description="M1 staging gate: snapshot / validate")
    sub = p.add_subparsers(dest="command", required=True)

    s = sub.add_parser("snapshot", help="freeze archive baselines (the only writing mode)")
    s.add_argument("--archive-trading", required=True)
    s.add_argument("--archive-history", required=True)
    s.add_argument("--calendar", required=True)
    s.add_argument("--baseline-out", required=True)
    s.add_argument("--force", action="store_true")
    s.set_defaults(func=cmd_snapshot)

    v = sub.add_parser("validate", help="validate staging against a frozen baseline")
    v.add_argument("--staging-trading", required=True)
    v.add_argument("--staging-history", required=True)
    v.add_argument("--archive-trading", required=True)
    v.add_argument("--archive-history", required=True)
    v.add_argument("--pilot-manifest", required=True)
    v.add_argument("--calendar", required=True)
    v.add_argument("--baseline", required=True)
    v.add_argument("--history-scope", choices=("all", "stocks"), default="all",
                   help="which manifest members the history view is declared to carry")
    v.add_argument("--pricing-basis", default="none")
    v.add_argument("--history-basis", default="qfq")
    v.add_argument("--transformation", default=None)
    v.add_argument("--identity-tolerance", type=float, default=0.005)
    v.add_argument("--warmup-consumers", choices=("pricing", "history", "both"),
                   default=None,
                   help="which view(s) actually supply feature warm-up")
    v.add_argument("--warmup-start", default=None)
    v.add_argument("--warmup-sessions", type=int, default=None)
    v.add_argument("--warmup-required", action="store_true")
    v.set_defaults(func=cmd_validate)
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except SystemExit2 as exc:
        print("input error: %s" % exc, file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
