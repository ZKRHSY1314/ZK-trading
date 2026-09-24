"""Independent closure probes; writes only disposable synthetic fixtures."""
from contextlib import closing
import csv
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


def emit(name, value):
    print(json.dumps({name: value}, ensure_ascii=False), flush=True)


def state():
    return {p.name: [p.stat().st_size, p.stat().st_mtime_ns]
            for name in ("trading_local.sqlite3", "market_history.sqlite3")
            for p in (ROOT / name, ROOT / (name + "-wal")) if p.exists()}


def hashes():
    return {name: hashlib.sha256((CLOSURE / name).read_bytes()).hexdigest()
            for name in ("staging_gate.py", "test_staging_gate_e2e.py", "pilot_symbols.csv")}


def main():
    before, artifacts_before = state(), hashes()
    emit("production_metadata_before", before)
    emit("artifact_hashes_before", artifacts_before)
    # Compute the fixture plan independently, without calling the gate's eligibility code.
    with demo.REAL_MANIFEST.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    stocks = [r for r in rows if r["stratum"] != "benchmark"]
    marks = [r for r in rows if r["stratum"] == "benchmark"]
    assert len(stocks) == 50 and {r["symbol"] for r in marks} == {"SH000300", "SH000001"}
    plan = {r["symbol"]: [d for d in demo.WINDOW
                          if r["stratum"] == "benchmark" or d >= r["list_date"]]
            for r in rows}
    assert sum(map(len, plan.values())) == 36193
    with tempfile.TemporaryDirectory(prefix="codex_m1_key_contract_") as directory:
        tmp = Path(directory).resolve()
        at, ah, st, sh, baseline = [tmp / name for name in
                                   ("archive_t.sqlite3", "archive_h.sqlite3",
                                    "stage_t.sqlite3", "stage_h.sqlite3", "baseline.json")]
        assert all(p.parent == tmp for p in (at, ah, st, sh, baseline))
        tiny = {s: days[:2] for s, days in list(plan.items())[:2]}
        demo.build_views(at, ah, tiny)
        code, output = demo.run(["snapshot", "--archive-trading", str(at),
                                "--archive-history", str(ah), "--calendar", str(demo.CALENDAR),
                                "--baseline-out", str(baseline)])
        assert code == 0, output
        protected = {p: demo.sha(p) for p in (at, ah, baseline, demo.CALENDAR)}

        def validate(name, extra=(), manifest=demo.REAL_MANIFEST):
            code, output = demo.run(["validate", "--staging-trading", str(st),
                                    "--staging-history", str(sh), "--archive-trading", str(at),
                                    "--archive-history", str(ah), "--calendar", str(demo.CALENDAR),
                                    "--baseline", str(baseline), "--pilot-manifest", str(manifest),
                                    "--pricing-basis", "none", "--history-basis", "none",
                                    "--transformation", "identity"] + list(extra))
            emit(name, {"exit_code": code, "output": output})
            return code

        def mutate_history(sql, args=()):
            with closing(sqlite3.connect(sh)) as conn:
                conn.execute(sql, args)
                conn.commit()

        victim = stocks[0]["symbol"]
        demo.build_views(st, sh, plan)
        assert validate("actual_manifest_clean_control") == 0
        mutate_history("DELETE FROM daily_bars WHERE symbol=? AND trade_date=?",
                       (victim, plan[victim][3]))
        assert validate("missing_history_record_rejected") == 1
        demo.build_views(st, sh, plan)
        mutate_history("UPDATE daily_bars SET symbol='XX123456' WHERE symbol=?", (victim,))
        assert validate("substituted_history_series_rejected") == 1
        demo.build_views(st, sh, plan, history_basis="qfq")
        assert validate("stored_basis_mismatch_rejected") == 1
        demo.build_views(st, sh, plan)
        mutate_history("UPDATE daily_bars SET high=12 WHERE symbol=? AND trade_date=?",
                       (victim, plan[victim][3]))
        assert validate("changed_high_rejected") == 1
        demo.build_views(st, sh, plan)
        assert validate("required_warmup_derived_and_short", ["--warmup-required", "--warmup-sessions", "250"]) == 1
        assert validate("required_warmup_incomplete_config", ["--warmup-required"]) == 2

        # Same unexpected key in BOTH views evades union-only reconciliation.
        ipo = next(r for r in stocks if r["list_date"] > demo.WINDOW[0])
        extra_day = next(d for d in reversed(demo.WINDOW) if d < ipo["list_date"])
        extra_plan = {s: list(days) for s, days in plan.items()}
        extra_plan[ipo["symbol"]].append(extra_day)
        demo.build_views(st, sh, extra_plan)
        emit("prelisting_injected_key", {"symbol": ipo["symbol"], "list_date": ipo["list_date"],
                                         "invalid_session": extra_day})
        validate("same_prelisting_record_in_both_views")

        # A diagnostic sub-batch of pre-window-listed stocks isolates warm-up logic.
        # This fixture is NOT a proposal to change the approved pilot universe.
        warm_days = demo.sessions_between("2022-08-24", "2023-09-03")
        assert len(warm_days) == 250
        older = [r for r in stocks if r["list_date"] < warm_days[0]][:2]
        subset = older + marks
        subset_file = tmp / "warmup_fixture_manifest.csv"
        with subset_file.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(subset)
        warm_plan = {r["symbol"]: warm_days + demo.WINDOW for r in subset}
        flags = ["--warmup-required", "--warmup-sessions", "250"]
        demo.build_views(st, sh, warm_plan)
        assert validate("complete_two_view_250_warmup_control", flags, subset_file) == 0
        mutate_history("DELETE FROM daily_bars WHERE trade_date < '2023-09-04'")
        validate("history_warmup_entirely_absent", flags, subset_file)
        demo.build_views(st, sh, warm_plan)
        mutate_history("UPDATE daily_bars SET high=12 WHERE symbol=? AND trade_date=?",
                       (older[0]["symbol"], warm_days[5]))
        validate("history_warmup_high_diverges", flags, subset_file)

        emit("protected_inputs_unchanged", all(demo.sha(p) == h for p, h in protected.items()))
    emit("production_metadata_after", state())
    emit("production_unchanged", before == state())
    emit("reviewed_artifacts_unchanged", artifacts_before == hashes())


if __name__ == "__main__":
    main()
