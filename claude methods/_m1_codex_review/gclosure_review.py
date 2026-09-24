"""Independent G1-G3 closure probes: temporary fixtures only, no production writes."""
from contextlib import closing
import hashlib
import json
from pathlib import Path
import sqlite3
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
CLOSURE = ROOT / "claude methods/_m1_closure"
sys.path.insert(0, str(CLOSURE))
import test_staging_gate_e2e as demo
import staging_gate as gate


def emit(name, value):
    print(json.dumps({name: value}, ensure_ascii=False), flush=True)


def production_metadata():
    return {p.name: [p.stat().st_size, p.stat().st_mtime_ns]
            for name in ("trading_local.sqlite3", "market_history.sqlite3")
            for p in (ROOT / name, ROOT / (name + "-wal")) if p.exists()}


def artifact_hashes():
    return {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
            for name in ("staging_gate.py", "test_staging_gate_e2e.py",
                         "acceptance_runner.py", "pilot_symbols.csv")
            for p in (CLOSURE / name,)}


def outcome(code, output):
    return {"exit_code": code, "output": output}


def main():
    before, source_before = production_metadata(), artifact_hashes()
    emit("production_metadata_before", before)
    emit("reviewed_artifact_hashes", source_before)
    with tempfile.TemporaryDirectory(prefix="codex_m1_gclosure_") as directory:
        tmp = Path(directory).resolve()
        at, ah, st, sh = [tmp / name for name in
                          ("archive_t.sqlite3", "archive_h.sqlite3", "stage_t.sqlite3", "stage_h.sqlite3")]
        baseline, manifest = tmp / "baseline.json", tmp / "pilot.csv"
        assert all(p.parent == tmp for p in (at, ah, st, sh, baseline, manifest))
        demo.make_trading(at, sessions=demo.WINDOW[:2])
        demo.make_history(ah, sessions=demo.WINDOW[:2])
        demo.write_manifest(manifest)
        code, output = demo.run(["snapshot", "--archive-trading", str(at),
                                "--archive-history", str(ah), "--calendar", str(demo.CALENDAR),
                                "--baseline-out", str(baseline)])
        assert code == 0, output
        protected = {p: demo.sha(p) for p in (at, ah, baseline, demo.CALENDAR)}

        def reset():
            demo.make_trading(st)
            demo.make_history(sh)

        def validate(extra=(), selected=manifest, expected=5):
            return demo.run(["validate", "--staging-trading", str(st),
                             "--staging-history", str(sh), "--archive-trading", str(at),
                             "--archive-history", str(ah), "--pilot-manifest", str(selected),
                             "--calendar", str(demo.CALENDAR), "--baseline", str(baseline),
                             "--expected-sessions", str(len(demo.WINDOW)),
                             "--expected-history-symbols", str(expected),
                             "--expected-history-sessions", str(len(demo.WINDOW)),
                             "--pricing-basis", "none", "--history-basis", "none",
                             "--transformation", "identity"] + list(extra))

        def mutate(sql, args=()):
            with closing(sqlite3.connect(sh)) as conn:
                conn.execute(sql, args)
                conn.commit()

        reset()
        emit("clean_two_view_control", outcome(*validate()))

        mutate("DELETE FROM daily_bars WHERE symbol=? AND trade_date=?",
               (demo.STOCKS[0], demo.WINDOW[20]))
        emit("one_required_history_key_missing", outcome(*validate()))

        reset()
        mutate("UPDATE daily_bars SET symbol='XX123456' WHERE symbol=?", (demo.STOCKS[0],))
        emit("history_stock_replaced_with_unknown_symbol", outcome(*validate()))

        reset()
        mutate("UPDATE daily_bars SET adjustment_mode='qfq'")
        emit("actual_qfq_history_declared_as_none", outcome(*validate()))

        reset()
        mutate("UPDATE daily_bars SET high=12 WHERE symbol=? AND trade_date=?",
               (demo.STOCKS[0], demo.WINDOW[20]))
        emit("identity_high_diverges_but_close_matches", outcome(*validate()))

        reset()
        emit("required_250_warmup_without_start", outcome(*validate(
            ["--warmup-required", "--warmup-sessions", "250"])))

        # Use the ACTUAL proposed pilot manifest, never edit it. Give every stock all
        # eligible bars and both indices the full window in both disposable stores.
        actual_manifest = CLOSURE / "pilot_symbols.csv"
        stocks, benchmarks = gate.load_manifest(actual_manifest)
        entries = stocks + benchmarks
        assert len(stocks) == 50 and len(benchmarks) == 2
        demo.make_trading(st, symbols=[e["symbol"] for e in entries])
        demo.make_history(sh, symbols=[e["symbol"] for e in entries])
        for path, table in ((st, "daily_bar_cache"), (sh, "daily_bars")):
            with closing(sqlite3.connect(path)) as conn:
                for entry in stocks:
                    assert entry["list_date"], entry
                    conn.execute("DELETE FROM %s WHERE symbol=? AND trade_date<?" % table,
                                 (entry["symbol"], entry["list_date"]))
                conn.commit()
        emit("actual_manifest_clean_50_plus_2", outcome(*validate(
            selected=actual_manifest, expected=52)))

        code, output = demo.run(["snapshot", "--archive-trading", str(at),
                                "--archive-history", str(ah), "--calendar", str(demo.CALENDAR),
                                "--baseline-out", str(at), "--force"])
        emit("protected_output_collision", outcome(code, output))
        emit("protected_fixture_inputs_unchanged", all(demo.sha(p) == v for p, v in protected.items()))

    emit("production_metadata_after", production_metadata())
    emit("production_main_and_wal_unchanged", before == production_metadata())
    emit("reviewed_artifacts_unchanged", source_before == artifact_hashes())


if __name__ == "__main__":
    main()
