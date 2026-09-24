"""End-to-end proof through the REAL command line.

Everything runs against TEMPORARY databases inside a TemporaryDirectory, driven through
`staging_gate.main(argv)`. A unit test of a check does not prove the command calls it.

This suite is a SUPERSET of every earlier CLI scenario. The acceptance review noted that
an unchanged count of 36 did not establish preservation, because several earlier cases had
been replaced. Each block below is labelled with the round that introduced it, and the
restored ones are marked [restored].

  G3    path-role safety (accepted)
  G1a   per-key membership: deleted record, substituted series
  G1b   stored representation and OHLC identity
  G2a   the ACTUAL delivered 50+2 manifest
  G2b   required warm-up may never become advisory
  G1r   [restored] history malformed date / price / duplicate / dangling FK,
        missing + unsupported transformation, mismatched bases, unknown eligibility
  K1    unexpected keys for a KNOWN security (pre-listing / post-delisting)
  K2    the declared warm-up consumer boundary
"""

from __future__ import annotations

import contextlib
import hashlib
import io
import os
import sqlite3
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import staging_gate  # noqa: E402
from staging_gate import entry_eligibility, load_manifest  # noqa: E402
from coverage_gap_generator import sessions_between  # noqa: E402

ROOT = Path(r"D:\codex-A股交易")
PROD = [ROOT / "trading_local.sqlite3", ROOT / "market_history.sqlite3"]
CALENDAR = ROOT / "backend/.venv/Lib/site-packages/akshare/file_fold/calendar.json"
REAL_MANIFEST = HERE / "pilot_symbols.csv"

WINDOW = sessions_between("2023-09-04", "2026-09-04")
ALL_SESSIONS = sessions_between("1990-12-19", "2026-12-31")
PRE = [s for s in ALL_SESSIONS if s < "2023-09-04"]
WARM = PRE[-250:]                       # the derived 250-session warm-up interval

TRADING_DDL = """
CREATE TABLE daily_bar_cache (
    symbol TEXT, trade_date TEXT, open REAL, high REAL, low REAL, close REAL,
    volume REAL, amount REAL, source TEXT, quality_status TEXT,
    adjustment_mode TEXT, volume_unit TEXT
);
CREATE TABLE instruments (symbol TEXT PRIMARY KEY, name TEXT);
"""
HISTORY_DDL = """
CREATE TABLE daily_bars (
    symbol TEXT, trade_date TEXT, adjustment_mode TEXT, open REAL, high REAL, low REAL,
    close REAL, volume REAL, amount REAL, provider TEXT, fetched_at TEXT,
    ingest_run_id INTEGER
);
CREATE TABLE ingest_runs (id INTEGER PRIMARY KEY, provider TEXT);
"""

OPEN, HIGH, LOW, CLOSE = 10.0, 11.0, 9.0, 10.5


def eligible_plan(manifest_path, window=WINDOW):
    stocks, marks = load_manifest(Path(manifest_path))
    plan = {}
    for entry in stocks + marks:
        elig, _ = entry_eligibility(entry, window)
        plan[entry["symbol"]] = list(elig)
    return plan, stocks, marks


def merge(*plans):
    out = {}
    for plan in plans:
        for sym, days in plan.items():
            out.setdefault(sym, [])
            out[sym] = sorted(set(out[sym]) | set(days))
    return out


def build_views(trading, history, plan, basis="none", history_plan=None,
                history_basis=None, run_id=1):
    for path, ddl in ((trading, TRADING_DDL), (history, HISTORY_DDL)):
        if path.exists():
            path.unlink()
        conn = sqlite3.connect(path)
        conn.executescript(ddl)
        conn.commit(); conn.close()

    tc = sqlite3.connect(trading)
    for sym, days in plan.items():
        tc.execute("INSERT OR IGNORE INTO instruments VALUES (?,'fixture')", (sym,))
        for day in days:
            tc.execute("INSERT INTO daily_bar_cache VALUES (?,?,?,?,?,?,1000.0,1050000.0,"
                       "'sina','ready',?,'hand')", (sym, day, OPEN, HIGH, LOW, CLOSE, basis))
    tc.commit(); tc.close()

    hc = sqlite3.connect(history)
    hc.execute("INSERT INTO ingest_runs VALUES (1,'sina')")
    for sym, days in (history_plan if history_plan is not None else plan).items():
        for day in days:
            hc.execute("INSERT INTO daily_bars VALUES (?,?,?,?,?,?,?,1000,NULL,'sina',"
                       "'2026-06-30T04:55:30+08:00',?)",
                       (sym, day, history_basis or basis, OPEN, HIGH, LOW, CLOSE, run_id))
    hc.commit(); hc.close()


def run(argv):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
        code = staging_gate.main(argv)
    return code, buf.getvalue()


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def prod_state():
    return {str(p): (p.stat().st_size, p.stat().st_mtime_ns) for p in PROD}


def main():
    before_prod = prod_state()
    failures, log = 0, []

    def check(label, ok, note=""):
        nonlocal failures
        failures += not ok
        log.append(("ok" if ok else "XX", label, note))

    with tempfile.TemporaryDirectory(prefix="m1gate_") as tmp:
        tmp = Path(tmp)
        arch_t, arch_h = tmp / "archive_trading.sqlite3", tmp / "archive_history.sqlite3"
        stag_t, stag_h = tmp / "staging_trading.sqlite3", tmp / "staging_history.sqlite3"
        baseline = tmp / "baseline.json"

        plan, stocks, marks = eligible_plan(REAL_MANIFEST)
        total = sum(len(v) for v in plan.values())
        build_views(arch_t, arch_h, {s: d[:2] for s, d in list(plan.items())[:2]})

        code, _ = run(["snapshot", "--archive-trading", str(arch_t),
                       "--archive-history", str(arch_h), "--calendar", str(CALENDAR),
                       "--baseline-out", str(baseline)])
        check("G3 normal baseline creation succeeds", code == 0 and baseline.exists(),
              "exit=%d" % code)
        frozen = baseline.read_bytes()
        at_sha, ah_sha, cal_sha = sha(arch_t), sha(arch_h), sha(CALENDAR)

        # ============================================================== G3 (retained)
        def snap(out, extra=()):
            return run(["snapshot", "--archive-trading", str(arch_t),
                        "--archive-history", str(arch_h), "--calendar", str(CALENDAR),
                        "--baseline-out", str(out)] + list(extra))

        check("G3 baseline-out == archive rejected even with --force",
              snap(arch_t, ["--force"])[0] == 2)
        check("G3 rejected write left the archive byte-identical", sha(arch_t) == at_sha)
        (tmp / "sub").mkdir(exist_ok=True)
        check("G3 normalized-path alias of an archive rejected",
              snap(tmp / "sub" / ".." / "archive_history.sqlite3", ["--force"])[0] == 2)
        check("G3 archive unchanged after normalized-alias rejection", sha(arch_h) == ah_sha)
        check("G3 baseline-out == calendar rejected", snap(CALENDAR, ["--force"])[0] == 2)
        check("G3 calendar unchanged", sha(CALENDAR) == cal_sha)
        if os.name == "nt":
            check("G3 case-insensitive alias rejected on Windows",
                  snap(tmp / "ARCHIVE_TRADING.SQLITE3", ["--force"])[0] == 2)
            check("G3 archive unchanged after case-alias rejection", sha(arch_t) == at_sha)
        link = tmp / "hardlink_archive.sqlite3"
        try:
            os.link(arch_t, link)
            check("G3 filesystem hardlink alias rejected", snap(link, ["--force"])[0] == 2)
            check("G3 archive unchanged after hardlink rejection", sha(arch_t) == at_sha)
        except OSError:
            log.append(("--", "G3 hardlink alias (unsupported here)", ""))
        check("G3 archive-trading == archive-history rejected",
              run(["snapshot", "--archive-trading", str(arch_t), "--archive-history",
                   str(arch_t), "--calendar", str(CALENDAR),
                   "--baseline-out", str(tmp / "b2.json")])[0] == 2)
        check("G3 replacing an existing baseline needs --force", snap(baseline)[0] == 2)
        check("G3 permitted baseline replacement with --force succeeds",
              snap(baseline, ["--force"])[0] == 0)
        decoy = tmp / "not_a_baseline.json"
        decoy.write_text('{"kind":"something_else"}', encoding="utf-8")
        check("G3 --force refuses to replace a non-baseline file",
              snap(decoy, ["--force"])[0] == 2)
        baseline.write_bytes(frozen)

        def validate(extra=(), manifest=REAL_MANIFEST, base_args=None):
            args = base_args if base_args is not None else [
                "--pricing-basis", "none", "--history-basis", "none",
                "--transformation", "identity"]
            return run(["validate",
                        "--staging-trading", str(stag_t), "--staging-history", str(stag_h),
                        "--archive-trading", str(arch_t), "--archive-history", str(arch_h),
                        "--pilot-manifest", str(manifest), "--calendar", str(CALENDAR),
                        "--baseline", str(baseline)] + args + list(extra))

        # ====================================================== G2a the REAL manifest
        build_views(stag_t, stag_h, plan)
        code, out = validate()
        check("G2a ACTUAL 50+2 manifest with complete data SUCCEEDS", code == 0,
              "exit=%d, %d stocks + %d benchmarks, %d records/view"
              % (code, len(stocks), len(marks), total))
        check("G2a benchmarks resolved without a fabricated IPO date", "unresolved=0" in out)

        bench = marks[0]["symbol"]
        p = {s: list(d) for s, d in plan.items()}; p[bench] = p[bench][:-1]
        build_views(stag_t, stag_h, p)
        check("G2a missing required BENCHMARK session fails", validate()[0] == 1)

        # ================================================ K1 unexpected keys, known symbol
        target = next(e for e in stocks if e["list_date"] == "2024-05-30")
        sym = target["symbol"]
        before_listing = max(s for s in WINDOW if s < target["list_date"])
        p = {s: list(d) for s, d in plan.items()}
        p[sym] = sorted(set(p[sym]) | {before_listing})     # SAME key added to BOTH views
        build_views(stag_t, stag_h, p)
        code, out = validate()
        check("K1 pre-listing record present in BOTH views fails", code == 1,
              "exit=%d, %s @ %s (declared list_date %s), %d records/view"
              % (code, sym, before_listing, target["list_date"], total + 1))
        check("K1 the ineligible record names the security and session",
              sym in out and before_listing in out and "ineligible_records" in out)

        delisted = tmp / "delisted.csv"
        delisted.write_text(
            "symbol,stratum,list_date,delist_date\n"
            "%s,ordinary_control,2020-01-02,2025-01-10\n"
            "SH000300,benchmark,,\n" % sym, encoding="utf-8")
        dplan, dstocks, dmarks = eligible_plan(delisted)
        after_delist = min(s for s in WINDOW if s > "2025-01-10")
        dplan[sym] = sorted(set(dplan[sym]) | {after_delist})
        build_views(stag_t, stag_h, dplan)
        code, out = validate(manifest=delisted)
        check("K1 declared post-delisting record fails", code == 1,
              "exit=%d, %s @ %s (declared delist 2025-01-10)" % (code, sym, after_delist))

        # ====================================================== G1a per-key membership
        victim = stocks[0]["symbol"]
        hp = {s: list(d) for s, d in plan.items()}; hp[victim] = hp[victim][:-1]
        build_views(stag_t, stag_h, plan, history_plan=hp)
        code, out = validate()
        check("G1a single missing HISTORY record fails", code == 1, "exit=%d" % code)
        check("G1a the missing record is named", victim in out)

        hp = {s: list(d) for s, d in plan.items()}; hp["XX123456"] = hp.pop(victim)
        build_views(stag_t, stag_h, plan, history_plan=hp)
        code, out = validate()
        check("G1a substituted HISTORY symbol fails", code == 1, "exit=%d" % code)
        check("G1a substitution reported in both directions",
              "unexpected_symbols" in out and "absent" in out)

        # ====================================================== G1b representation
        build_views(stag_t, stag_h, plan, basis="none", history_basis="qfq")
        check("G1b stored history basis 'qfq' vs declared 'none' fails", validate()[0] == 1)

        build_views(stag_t, stag_h, plan)
        c = sqlite3.connect(stag_h)
        c.execute("UPDATE daily_bars SET adjustment_mode='qfq' WHERE symbol=?", (victim,))
        c.commit(); c.close()
        check("G1b MIXED stored bases in one view fails", validate()[0] == 1)

        for field in ("open", "high", "low"):
            build_views(stag_t, stag_h, plan)
            c = sqlite3.connect(stag_h)
            c.execute("UPDATE daily_bars SET %s = %s + 1.0 WHERE symbol=? AND trade_date=?"
                      % (field, field), (victim, plan[victim][3]))
            c.commit(); c.close()
            check("G1b changed %-4s with close unchanged fails identity" % field,
                  validate()[0] == 1)

        # ========================================== G1r [restored] earlier CLI scenarios
        def corrupt_history(fn):
            build_views(stag_t, stag_h, plan)
            c = sqlite3.connect(stag_h); fn(c); c.commit(); c.close()
            return validate()

        check("G1r [restored] malformed HISTORY date fails",
              corrupt_history(lambda c: c.execute(
                  "UPDATE daily_bars SET trade_date='ERROR' WHERE symbol=? AND trade_date=?",
                  (victim, plan[victim][5])))[0] == 1)
        check("G1r [restored] nonpositive HISTORY price fails",
              corrupt_history(lambda c: c.execute(
                  "UPDATE daily_bars SET close=-999, high=1, low=100 "
                  "WHERE symbol=? AND trade_date=?", (victim, plan[victim][5])))[0] == 1)
        check("G1r [restored] duplicate HISTORY key fails",
              corrupt_history(lambda c: c.execute(
                  "INSERT INTO daily_bars SELECT * FROM daily_bars "
                  "WHERE symbol=? AND trade_date=? LIMIT 1",
                  (victim, plan[victim][5])))[0] == 1)
        check("G1r [restored] dangling HISTORY ingest_run_id fails",
              corrupt_history(lambda c: c.execute(
                  "UPDATE daily_bars SET ingest_run_id=42 WHERE symbol=?", (victim,)))[0] == 1)

        build_views(stag_t, stag_h, plan)
        check("G1r [restored] MISSING transformation blocks acceptance",
              validate(base_args=["--pricing-basis", "none", "--history-basis", "none"])[0] == 1)
        check("G1r [restored] UNSUPPORTED transformation blocks acceptance",
              validate(base_args=["--pricing-basis", "none", "--history-basis", "none",
                                  "--transformation", "affine_split_adjust"])[0] == 1)
        check("G1r [restored] identity declared across DIFFERENT bases fails",
              validate(base_args=["--pricing-basis", "none", "--history-basis", "qfq",
                                  "--transformation", "identity"])[0] == 1)

        unknown = tmp / "unknown.csv"
        unknown.write_text("symbol,stratum,list_date,delist_date\n"
                           "%s,ordinary_control,,\nSH000300,benchmark,,\n" % victim,
                           encoding="utf-8")
        uplan, _, _ = eligible_plan(unknown)
        uplan[victim] = list(plan[victim])
        build_views(stag_t, stag_h, uplan)
        code, out = validate(manifest=unknown)
        check("G1r [restored] unknown eligibility is UNRESOLVED, not complete",
              code == 1 and "unresolved=1" in out, "exit=%d" % code)

        # ============================================ K2 warm-up consumer boundary
        # Diagnostic subset for warm-up isolation only. The APPROVED pilot population is
        # unchanged; this subset is never proposed as the pilot.
        subset_syms = [e for e in stocks if e["list_date"] and e["list_date"] < WARM[0]][:2]
        subset = tmp / "warmup_subset.csv"
        subset.write_text(
            "symbol,stratum,list_date,delist_date\n"
            + "".join("%s,ordinary_control,%s,\n" % (e["symbol"], e["list_date"])
                      for e in subset_syms)
            + "".join("%s,benchmark,,\n" % m["symbol"] for m in marks), encoding="utf-8")
        sub_research, sub_stocks, sub_marks = eligible_plan(subset)
        sub_warm, _, _ = eligible_plan(subset, window=WARM)
        full = merge(sub_research, sub_warm)

        WARM_ARGS = ["--pricing-basis", "none", "--history-basis", "none",
                     "--transformation", "identity"]

        build_views(stag_t, stag_h, full)
        check("K2 warm-up requested without --warmup-consumers is an input error",
              validate(["--warmup-start", WARM[0]], manifest=subset,
                       base_args=WARM_ARGS)[0] == 2)

        code, out = validate(["--warmup-consumers", "both", "--warmup-sessions", "250",
                              "--warmup-required"], manifest=subset, base_args=WARM_ARGS)
        check("K2 clean eligible warm-up in BOTH views is ready", code == 0,
              "exit=%d, %d securities" % (code, len(sub_stocks) + len(sub_marks)))

        build_views(stag_t, stag_h, full, history_plan=sub_research)   # history warm-up gone
        code, out = validate(["--warmup-consumers", "both", "--warmup-sessions", "250",
                              "--warmup-required"], manifest=subset, base_args=WARM_ARGS)
        check("K2 absent HISTORY warm-up blocks when history is a declared consumer",
              code == 1, "exit=%d" % code)

        code, out = validate(["--warmup-consumers", "pricing", "--warmup-sessions", "250",
                              "--warmup-required"], manifest=subset, base_args=WARM_ARGS)
        check("K2 same data passes when only pricing is declared consumed", code == 0,
              "exit=%d" % code)
        check("K2 the unconsumed view is declared, not silently certified",
              "NOT CONSUMED" in out and "scope=pricing" in out)

        build_views(stag_t, stag_h, full)
        c = sqlite3.connect(stag_h)
        c.execute("UPDATE daily_bars SET high = high + 1.0 WHERE symbol=? AND trade_date=?",
                  (sub_stocks[0]["symbol"], WARM[10]))
        c.commit(); c.close()
        code, out = validate(["--warmup-consumers", "both", "--warmup-sessions", "250",
                              "--warmup-required"], manifest=subset, base_args=WARM_ARGS)
        check("K2 divergent WARM-UP high blocks when both views are consumed", code == 1,
              "exit=%d" % code)
        code, out = validate(["--warmup-consumers", "pricing", "--warmup-sessions", "250",
                              "--warmup-required"], manifest=subset, base_args=WARM_ARGS)
        check("K2 the same divergence is out of scope for a pricing-only contract",
              code == 0, "exit=%d" % code)

        build_views(stag_t, stag_h, full)
        code, out = validate(["--warmup-consumers", "both", "--warmup-sessions", "250"],
                             manifest=subset, base_args=WARM_ARGS)
        check("K2 legitimate warm-up is not counted as an unexpected research record",
              code == 0 and "ineligible_records" not in out, "exit=%d" % code)
        check("K2 warm-up interval does not overlap the research window",
              "research starts 2023-09-04, overlap=0" in out)

        # New listing: complete eligible price coverage, insufficient feature observations.
        ipo = next((e for e in stocks if e["list_date"] > WARM[-1]), None)
        if ipo:
            ipo_man = tmp / "ipo.csv"
            ipo_man.write_text("symbol,stratum,list_date,delist_date\n"
                               "%s,ordinary_control,%s,\nSH000300,benchmark,,\n"
                               % (ipo["symbol"], ipo["list_date"]), encoding="utf-8")
            ip, _, _ = eligible_plan(ipo_man)
            iw, _, _ = eligible_plan(ipo_man, window=WARM)
            build_views(stag_t, stag_h, merge(ip, iw))
            code, out = validate(["--warmup-consumers", "both", "--warmup-sessions", "250",
                                  "--warmup-required"], manifest=ipo_man, base_args=WARM_ARGS)
            check("K2 new listing: complete M1 coverage but insufficient warm-up is FAIL",
                  code == 1, "exit=%d (%s listed %s)" % (code, ipo["symbol"], ipo["list_date"]))
            check("K2 that shortfall is stated as readiness, not as missing coverage",
                  "short=1" in out
                  and "complete eligible price coverage is gate m1" in out.lower())

        # ====================================================== G2b [restored]
        build_views(stag_t, stag_h, full)
        code, out = validate(["--warmup-consumers", "pricing", "--warmup-required",
                              "--warmup-sessions", "250"], manifest=subset,
                             base_args=WARM_ARGS)
        check("G2b [restored] required warm-up with no start derives the interval",
              code == 0, "exit=%d" % code)
        check("G2b [restored] required warm-up with neither start nor depth is exit 2",
              validate(["--warmup-consumers", "pricing", "--warmup-required"],
                       manifest=subset, base_args=WARM_ARGS)[0] == 2)
        code, out = validate(["--warmup-consumers", "pricing", "--warmup-start", WARM[0]],
                             manifest=subset, base_args=WARM_ARGS)
        check("G2b [restored] advisory warm-up does not block a clean run", code == 0,
              "exit=%d" % code)

        # ================================ K1e empty eligible domains (research)
        # Synthetic listing metadata in disposable manifests only. The approved
        # manifest is never modified, and these say nothing about the real listing
        # history of the securities whose identifiers they reuse.
        probe = stocks[0]["symbol"] if stocks[0]["symbol"] != bench else stocks[1]["symbol"]
        inject_day = "2025-06-10"

        def empty_domain_manifest(name, list_date, delist_date=""):
            path = tmp / name
            path.write_text(
                "symbol,stratum,list_date,delist_date\n"
                "%s,ordinary_control,%s,%s\n"
                "SH000300,benchmark,,\n" % (probe, list_date, delist_date),
                encoding="utf-8")
            return path

        for label, man in (
            ("listed entirely AFTER the research window",
             empty_domain_manifest("after_window.csv", "2026-09-07")),
            ("delisted entirely BEFORE the research window",
             empty_domain_manifest("before_window.csv", "2000-01-01", "2023-09-01")),
        ):
            eplan, _, _ = eligible_plan(man)
            build_views(stag_t, stag_h, eplan)
            code, out = validate(manifest=man)
            check("K1e %s, correctly empty, is rejected on the MANIFEST" % label,
                  code == 1 and "MANIFEST REJECTED" in out and probe in out,
                  "exit=%d" % code)
            check("K1e %s, correctly empty, is not reported as absent data" % label,
                  "absent=[]" not in out and "correctly_empty=1" in out)

            injected = {k: list(v) for k, v in eplan.items()}
            injected[probe] = sorted(set(injected.get(probe, [])) | {inject_day})
            build_views(stag_t, stag_h, injected)
            code, out = validate(manifest=man)
            check("K1e %s, INJECTED record in both views, still fails" % label,
                  code == 1, "exit=%d" % code)
            check("K1e injected record is named as ineligible (%s)" % label.split()[1],
                  "ineligible_records" in out and probe in out and inject_day in out)

        # ================================ K1e empty warm-up domain is legitimate
        late = next((e for e in stocks
                     if e["list_date"] and WARM[-1] < e["list_date"] <= WINDOW[-1]), None)
        if late:
            lman = tmp / "late_listing.csv"
            lman.write_text("symbol,stratum,list_date,delist_date\n"
                            "%s,ordinary_control,%s,\nSH000300,benchmark,,\n"
                            % (late["symbol"], late["list_date"]), encoding="utf-8")
            lres, _, _ = eligible_plan(lman)
            lwarm, _, _ = eligible_plan(lman, window=WARM)
            build_views(stag_t, stag_h, merge(lres, lwarm))
            code, out = validate(["--warmup-consumers", "both", "--warmup-sessions", "250",
                                  "--warmup-required"], manifest=lman, base_args=WARM_ARGS)
            check("K1e empty WARM-UP domain is allowed, not a coverage failure",
                  "correctly_empty=1" in out and "empty_domain=allow" in out,
                  "%s listed %s" % (late["symbol"], late["list_date"]))
            check("K1e that security still FAILS required feature depth (distinct outcome)",
                  code == 1 and "short=" in out, "exit=%d" % code)

            bad = merge(lres, lwarm)
            bad[late["symbol"]] = sorted(set(bad[late["symbol"]]) | {WARM[5]})
            build_views(stag_t, stag_h, bad)
            code, out = validate(["--warmup-consumers", "both", "--warmup-sessions", "250",
                                  "--warmup-required"], manifest=lman, base_args=WARM_ARGS)
            check("K1e an ineligible WARM-UP record still fails and is named",
                  code == 1 and "ineligible_records" in out and WARM[5] in out,
                  "exit=%d" % code)

        # ================================ K1e known-empty is not UNKNOWN
        both_blank = tmp / "blank_and_empty.csv"
        both_blank.write_text("symbol,stratum,list_date,delist_date\n"
                              "%s,ordinary_control,,\nSH000300,benchmark,,\n" % probe,
                              encoding="utf-8")
        bplan, _, _ = eligible_plan(both_blank)
        bplan[probe] = list(plan[probe])
        build_views(stag_t, stag_h, bplan)
        code, out = validate(manifest=both_blank)
        check("K1e unknown eligibility stays UNRESOLVED, distinct from known-empty",
              code == 1 and "unresolved=1" in out and "known_empty=0" in out,
              "exit=%d" % code)

        check("frozen baseline byte-identical after every validation",
              baseline.read_bytes() == frozen)
        check("archive hashes unchanged after every validation",
              sha(arch_t) == at_sha and sha(arch_h) == ah_sha)

    check("production databases unchanged (size + mtime)", before_prod == prod_state())

    print("M1 staging gate end-to-end suite (real CLI, real 50+2 manifest)")
    for status, label, note in log:
        print("  [%s] %-68s %s" % (status, label, note))
    print("\n  %d checks, %d unexpected" % (len(log), failures))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
