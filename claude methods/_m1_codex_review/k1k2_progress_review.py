"""Bounded, independent K1/K2 progress review; only disposable fixture writes."""
from contextlib import closing
import csv
import hashlib
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
CLOSURE = ROOT / "claude methods/_m1_closure"
sys.path.insert(0, str(CLOSURE))
import test_staging_gate_e2e as fixture


def metadata():
    return {p.name: [p.stat().st_size, p.stat().st_mtime_ns]
            for name in ("trading_local.sqlite3", "market_history.sqlite3")
            for p in (ROOT / name, ROOT / (name + "-wal")) if p.exists()}


def main():
    before = metadata()
    watched = [CLOSURE / n for n in
               ("staging_gate.py", "test_staging_gate_e2e.py", "pilot_symbols.csv")]
    hashes = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in watched}
    with fixture.REAL_MANIFEST.open(encoding="utf-8", newline="") as handle:
        entries = list(csv.DictReader(handle))
    stocks = [e for e in entries if e["stratum"] != "benchmark"]
    marks = [e for e in entries if e["stratum"] == "benchmark"]
    assert len(stocks) == 50
    assert {e["symbol"] for e in marks} == {"SH000001", "SH000300"}
    # Independent expected-key construction, not the gate's eligibility function.
    plan = {e["symbol"]: [d for d in fixture.WINDOW
                         if (e["stratum"] == "benchmark" or d >= e["list_date"])
                         and (not e.get("delist_date") or d <= e["delist_date"])]
            for e in entries}
    assert sum(map(len, plan.values())) == 36193
    with tempfile.TemporaryDirectory(prefix="codex_k1k2_progress_") as directory:
        tmp = Path(directory).resolve()
        at, ah, st, sh, baseline = [tmp / n for n in
                                  ("at.sqlite3", "ah.sqlite3", "st.sqlite3",
                                   "sh.sqlite3", "baseline.json")]
        fixture.build_views(at, ah, {s: ds[:2] for s, ds in list(plan.items())[:2]})

        def cli(args):
            result = subprocess.run(
                [sys.executable, "-B", "-X", "utf8", str(CLOSURE / "staging_gate.py")]
                + args, text=True, encoding="utf-8", capture_output=True, check=False)
            return result.returncode, result.stdout + result.stderr

        code, out = cli(["snapshot", "--archive-trading", str(at),
                         "--archive-history", str(ah), "--calendar", str(fixture.CALENDAR),
                         "--baseline-out", str(baseline)])
        assert code == 0, out
        protected = {p: fixture.sha(p) for p in (at, ah, baseline, fixture.CALENDAR)}

        def validate(name, manifest=fixture.REAL_MANIFEST, flags=()):
            code, out = cli([
                "validate", "--staging-trading", str(st), "--staging-history", str(sh),
                "--archive-trading", str(at), "--archive-history", str(ah),
                "--calendar", str(fixture.CALENDAR), "--baseline", str(baseline),
                "--pilot-manifest", str(manifest), "--pricing-basis", "none",
                "--history-basis", "none", "--transformation", "identity"] + list(flags))
            interesting = [line.strip() for line in out.splitlines()
                           if any(k in line for k in ("RESULT:", "input error:",
                                  "pricing/stocks:", "history/all:", "warmup/", "scope=",
                                  "W1_", "W2 ", "V3b", "NOT CONSUMED"))]
            print(json.dumps({"case": name, "exit_code": code, "details": interesting},
                             ensure_ascii=False), flush=True)
            return code

        def manifest(name, rows):
            path = tmp / name
            with path.open("w", encoding="utf-8", newline="") as handle:
                fields = list(dict.fromkeys(k for row in rows for k in row))
                writer = csv.DictWriter(handle, fieldnames=fields)
                writer.writeheader()
                writer.writerows(rows)
            return path

        fixture.build_views(st, sh, plan)
        assert validate("actual_50_plus_2_clean_36193") == 0
        bad_plan = {s: list(ds) for s, ds in plan.items()}
        bad_plan["BJ920002"].append("2024-05-29")
        fixture.build_views(st, sh, bad_plan)
        assert validate("original_prelisting_probe_rejected") == 1

        # Same K1 domain requirement when the eligible set is EMPTY, not merely short.
        victim = stocks[0]["symbol"]
        for case, changes in (
            ("listed_after_research", {"list_date": "2026-09-07", "delist_date": ""}),
            ("delisted_before_research", {"list_date": "2000-01-01",
                                          "delist_date": "2023-09-01"}),
        ):
            altered = [dict(e, **changes) if e["symbol"] == victim else dict(e)
                       for e in entries]
            mf = manifest(case + ".csv", altered)
            empty = {s: list(ds) for s, ds in plan.items()}
            empty[victim] = []
            fixture.build_views(st, sh, empty)
            validate(case + "_correctly_empty", mf)
            empty[victim] = ["2025-06-10"]
            fixture.build_views(st, sh, empty)
            validate(case + "_one_ineligible_row_in_both_views", mf)

        # Diagnostic subset only; never changes the actual pilot manifest/universe.
        older = [e for e in stocks if e["list_date"] < fixture.WARM[0]][:2]
        mf = manifest("warmup_subset.csv", older + marks)
        full = {e["symbol"]: fixture.WARM + fixture.WINDOW for e in older + marks}
        flags = ["--warmup-consumers", "both", "--warmup-required",
                 "--warmup-sessions", "250"]
        fixture.build_views(st, sh, full)
        assert validate("warmup_both_clean", mf, flags) == 0
        with closing(sqlite3.connect(sh)) as conn:
            conn.execute("DELETE FROM daily_bars WHERE trade_date < '2023-09-04'")
            conn.commit()
        assert validate("warmup_missing_history_required", mf, flags) == 1
        pricing_flags = list(flags)
        pricing_flags[1] = "pricing"
        assert validate("warmup_missing_history_not_consumed", mf, pricing_flags) == 0
        fixture.build_views(st, sh, full)
        with closing(sqlite3.connect(sh)) as conn:
            conn.execute("UPDATE daily_bars SET high=12 WHERE symbol=? AND trade_date=?",
                         (older[0]["symbol"], fixture.WARM[5]))
            conn.commit()
        assert validate("warmup_divergent_high_required", mf, flags) == 1
        assert validate("warmup_divergent_history_not_consumed", mf, pricing_flags) == 0
        assert all(fixture.sha(p) == h for p, h in protected.items())
    assert before == metadata()
    assert all(hashlib.sha256(p.read_bytes()).hexdigest() == h for p, h in hashes.items())
    print(json.dumps({"production_unchanged": True, "reviewed_artifacts_unchanged": True,
                      "protected_inputs_unchanged": True, "production_metadata": before}))


if __name__ == "__main__":
    main()
