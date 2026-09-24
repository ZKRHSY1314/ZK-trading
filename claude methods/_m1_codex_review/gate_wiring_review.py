"""Review the real staging CLI using disposable fixtures, not production data.

This is a diagnostic reproducer of remaining defects, not a fix or download tool.
"""
import hashlib
import json
from contextlib import closing
from pathlib import Path
import sqlite3
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
CLOSURE = ROOT / "claude methods/_m1_closure"
sys.path.insert(0, str(CLOSURE))
import test_staging_gate_e2e as demo


def emit(name, value):
    print(json.dumps({name: value}, ensure_ascii=False), flush=True)


def state():
    return {p.name: [p.stat().st_size, p.stat().st_mtime_ns]
            for n in ("trading_local.sqlite3", "market_history.sqlite3")
            for p in (ROOT / n, ROOT / (n + "-wal")) if p.exists()}


def outcome(code, output):
    return {"exit_code": code,
            "result_lines": [line.strip() for line in output.splitlines()
                             if "RESULT:" in line or "V1 " in line or "V3 " in line],
            "D8_executed": any(line.strip().startswith("D8 ") for line in output.splitlines())}


def main():
    before = state()
    emit("production_metadata_before", before)
    with tempfile.TemporaryDirectory(prefix="codex_m1_wiring_") as directory:
        tmp = Path(directory).resolve()
        arch_t, arch_h = tmp / "archive_trading.sqlite3", tmp / "archive_history.sqlite3"
        stage_t, stage_h = tmp / "staging_trading.sqlite3", tmp / "staging_history.sqlite3"
        manifest, baseline = tmp / "pilot.csv", tmp / "baseline.json"
        for p in (arch_t, arch_h, stage_t, stage_h, manifest, baseline):
            assert p.parent == tmp  # All fixture writes stay inside this temporary directory.
        demo.make_trading(arch_t)
        demo.make_history(arch_h)
        demo.make_trading(stage_t)
        demo.make_history(stage_h)
        demo.write_manifest(manifest)
        code, output = demo.run(["snapshot", "--archive-trading", str(arch_t),
                                "--archive-history", str(arch_h), "--calendar", str(demo.CALENDAR),
                                "--baseline-out", str(baseline)])
        assert code == 0, output
        frozen = baseline.read_bytes()

        def validate(extra=()):
            return demo.run(["validate", "--staging-trading", str(stage_t),
                             "--staging-history", str(stage_h), "--archive-trading", str(arch_t),
                             "--archive-history", str(arch_h), "--pilot-manifest", str(manifest),
                             "--calendar", str(demo.CALENDAR), "--baseline", str(baseline),
                             "--expected-sessions", str(len(demo.WINDOW))] + list(extra))

        code, output = validate()
        emit("supplied_clean_fixture", outcome(code, output))
        with closing(sqlite3.connect(stage_h)) as c:
            emit("clean_fixture_history_shape", dict(zip(
                ["rows", "symbols", "sessions"], c.execute(
                    "SELECT COUNT(*),COUNT(DISTINCT symbol),COUNT(DISTINCT trade_date) FROM daily_bars"
                ).fetchone())))
            c.execute("UPDATE daily_bars SET trade_date='ERROR', close=-999, high=1, low=100, "
                      "provider='wrong_source'")
            c.execute("INSERT INTO daily_bars SELECT * FROM daily_bars LIMIT 1")
            c.commit()
        code, output = validate()
        emit("corrupt_history_still_validates", outcome(code, output))

        # A valid IPO has all sessions after listing and no fabricated pre-listing bars.
        demo.make_history(stage_h)
        listed = "2025-06-10"
        with closing(sqlite3.connect(stage_t)) as c:
            c.execute("ALTER TABLE instruments ADD COLUMN list_date TEXT")
            c.execute("UPDATE instruments SET list_date='1990-12-19'")
            c.execute("UPDATE instruments SET list_date=? WHERE symbol='SZ000001'", (listed,))
            c.execute("DELETE FROM daily_bar_cache WHERE symbol='SZ000001' AND trade_date<?", (listed,))
            expected = sum(day >= listed for day in demo.WINDOW)
            actual = c.execute("SELECT COUNT(*) FROM daily_bar_cache WHERE symbol='SZ000001'").fetchone()[0]
            c.commit()
        rows = ["symbol,stratum,list_date"]
        rows += [f"{s},ordinary_control,{listed if s == 'SZ000001' else '1990-12-19'}" for s in demo.STOCKS]
        rows += [f"{s},benchmark," for s in demo.MARKS]
        # Reuse a CSV writer rather than any production artifact writer.
        with manifest.open("w", encoding="utf-8", newline="") as f:
            f.write("\n".join(rows) + "\n")
        code, output = validate()
        emit("complete_ipo_rejected", {"eligible_post_listing_sessions": expected,
             "observed_post_listing_sessions": actual, **outcome(code, output)})
        emit("baseline_unchanged", baseline.read_bytes() == frozen)

        # Simulate an operator's path collision on a DISPOSABLE archive, never production.
        # --force is meant to replace a baseline, not destroy an input database.
        archive_before = hashlib.sha256(arch_t.read_bytes()).hexdigest()
        code, output = demo.run(["snapshot", "--archive-trading", str(arch_t),
                                "--archive-history", str(arch_h), "--calendar", str(demo.CALENDAR),
                                "--baseline-out", str(arch_t), "--force"])
        emit("snapshot_output_aliases_archive", {"exit_code": code,
             "archive_changed": hashlib.sha256(arch_t.read_bytes()).hexdigest() != archive_before,
             "still_sqlite_header": arch_t.read_bytes().startswith(b"SQLite format 3\x00")})
    after = state()
    emit("production_metadata_after", after)
    emit("production_main_and_wal_unchanged", before == after)


if __name__ == "__main__":
    main()
