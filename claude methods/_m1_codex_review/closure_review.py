"""Independent M1 closure checks; production read-only, defects in memory only.

Does not call artifact writers or overwrite Claude's frozen baseline.
"""
import csv
import hashlib
import json
from dataclasses import asdict, replace
from datetime import datetime
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
CLOSURE = ROOT / "claude methods/_m1_closure"
sys.path.insert(0, str(CLOSURE))
import coverage_gap_generator as cov
import temporal_contract as temporal
import acceptance_runner as gates
import test_acceptance_gates as fixtures
import pilot_selection as pilot


def emit(key, value):
    print(json.dumps({key: value}, ensure_ascii=False), flush=True)


def metadata():
    return {p.name: [p.stat().st_size, p.stat().st_mtime_ns]
            for name in ("trading_local.sqlite3", "market_history.sqlite3")
            for p in (ROOT / name, ROOT / (name + "-wal")) if p.exists()}


def synthetic_probes():
    empty_cache = fixtures.db(fixtures.CACHE_DDL)
    empty_history = fixtures.db(fixtures.BARS_DDL)
    emit("empty_tables", {
        "D1": gates.chk_dates(empty_cache), "D2": gates.chk_symbols(empty_cache),
        "D3": gates.chk_prices(empty_cache), "D5": gates.chk_provenance(empty_history)})

    null_unit = fixtures.db(fixtures.CACHE_DDL)
    fixtures.cache_row(null_unit, amount=1_050_000.0, unit=None, adj="none")
    emit("null_volume_unit", gates.chk_units(null_unit))

    blank = replace(temporal.GENUINE, observed_availability="", ingestion_time="",
                    factor_vintage="", provenance="")
    emit("blank_temporal_provenance", asdict(temporal.admit(blank, temporal.CUTOFF, temporal.STRICT_PIT)))

    cutoff = "2024-06-28T10:00:00+08:00"  # 02:00 UTC
    observed = "2024-06-28T03:00:00Z"      # one hour AFTER cutoff
    zoned = replace(temporal.GENUINE, observed_availability=observed,
                    ingestion_time=observed)
    emit("mixed_timezone_later_version", {
        "really_after_cutoff": datetime.fromisoformat(observed) > datetime.fromisoformat(cutoff),
        "admission": asdict(temporal.admit(zoned, cutoff, temporal.STRICT_PIT))})

    archive = fixtures._archive(10.0)
    archive.execute("ALTER TABLE daily_bars ADD COLUMN open REAL DEFAULT 9.0")
    archive.execute("ALTER TABLE daily_bars ADD COLUMN provider TEXT DEFAULT 'source_A'")
    baseline = gates.archive_fingerprint(archive)
    archive.execute("UPDATE daily_bars SET open=9999.0, provider='tampered' WHERE symbol='SH600000'")
    emit("archive_open_and_provenance_tamper", gates.chk_archive(archive, baseline))

    # A duplicated bar does not violate dates, namespace, prices, units or run FK.
    duplicated = fixtures.db(fixtures.CACHE_DDL)
    for _ in range(2):
        fixtures.cache_row(duplicated, amount=1_050_000.0, unit="hand", adj="none")
    emit("duplicate_bar_gates", {
        "rows": duplicated.execute("SELECT COUNT(*) FROM daily_bar_cache").fetchone()[0],
        "D1": gates.chk_dates(duplicated), "D2": gates.chk_symbols(duplicated),
        "D3": gates.chk_prices(duplicated), "D4": gates.chk_units(duplicated)})

    # Planned benchmark must be tested separately from the stock catalog.
    benchmark = fixtures.db(fixtures.CACHE_DDL)
    fixtures.cache_row(benchmark, symbol="SH000300", register=False, amount=None, adj="none", unit="unknown")
    emit("benchmark_without_stock_catalog_entry", {
        "D2": gates.chk_symbols(benchmark), "D4": gates.chk_units(benchmark)})
    for c in (empty_cache, empty_history, null_unit, archive, duplicated, benchmark):
        c.close()


def readonly_artifact_checks():
    before = metadata()
    emit("production_metadata_before", before)
    paths = [CLOSURE / p for p in ("coverage_reconciled.csv", "coverage_reconciled_meta.json",
                                   "acceptance_baseline.json", "pilot_symbols.csv")]
    input_hashes = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    result = cov.build()  # no call to cov.write()
    frozen = json.loads((CLOSURE / "coverage_reconciled_meta.json").read_text(encoding="utf-8"))
    with (CLOSURE / "coverage_reconciled.csv").open(encoding="utf-8", newline="") as f:
        saved_rows = list(csv.DictReader(f))
    comparable = [{k: str(v) for k, v in r.items()} for r in result["records"]]
    emit("coverage_reproduction", {
        "all_csv_cells_match": comparable == saved_rows,
        "totals_match": result["totals"] == frozen["totals"],
        "calendar_hash_matches_record": cov.CALENDAR_SHA256 == frozen["calendar_sha256"],
        "totals": result["totals"],
        "BJ920000": next(r for r in result["records"] if r["symbol"] == "BJ920000")})

    picks = pilot.select()  # read only, no CSV/meta writer
    with (CLOSURE / "pilot_symbols.csv").open(encoding="utf-8", newline="") as f:
        saved_picks = list(csv.DictReader(f))
    emit("pilot_reproduction", {
        "exact_csv_match": [{k: str(v) for k, v in r.items()} for r in picks] == saved_picks,
        "n": len(picks), "unique": len({r["symbol"] for r in picks}),
        "strata": {s: sum(r["stratum"] == s for r in picks) for s in pilot.QUOTA},
        "benchmarks": pilot.BENCHMARKS})

    # Run the current production diagnostic function, NOT its __main__ baseline writer.
    actual = gates.production_run()
    baseline = json.loads((CLOSURE / "acceptance_baseline.json").read_text(encoding="utf-8"))
    emit("production_diagnostic", actual)
    emit("production_matches_frozen", actual == baseline["results"])
    emit("input_artifacts_unchanged", input_hashes == {
        p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in paths})
    emit("production_metadata_after", metadata())
    emit("production_main_and_wal_unchanged", before == metadata())


if __name__ == "__main__":
    synthetic_probes()
    readonly_artifact_checks()
