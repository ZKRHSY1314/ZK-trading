"""Versioned real-session staging. Reuses V1 storage/atomic-publication guards.

V1 gate runs are retained unchanged. V2 substitutes only approved calendar and
price-domain semantics in an isolated gate invocation, then restores the module.
Every stored price, quantity and lineage field is also checked against raw replay.
"""
from contextlib import redirect_stderr, redirect_stdout
import io
import json
from pathlib import Path
import sqlite3
from urllib.parse import quote

import contract_v2 as contract
import staging as old
import run_actual_staging as guard

require, sha, read = old._require, old._sha, guard.read_json


def check_gate_acceptance(text, code, mode, shortfalls):
    _, acceptance = old._legacy_modules()
    required = acceptance.RESEARCH_REQUIRED if mode == "research" else acceptance.WARMUP_REQUIRED
    gates = acceptance.parse_gate_output(text, code, expected_ids=required)
    acceptance.enforce_inventory(gates, required)
    failing = {g.id for g in gates if g.required and g.status not in acceptance.SUCCESSFUL}
    if mode == "research":
        require(not failing, "v2_research_gate_failed")
    else:
        require(failing == {"V3b"}, "v2_unexpected_warmup_gate_failure")
        require(shortfalls == contract.SHORT, "v2_unexpected_listing_depth_shortfall")
    return {g.id: g.status for g in gates}


class StagingRunV2(old.StagingRun):
    def __init__(self, root, run_id, qualification_path, reviewed_sha):
        qualification_path = Path(qualification_path).resolve()
        require(qualification_path.parent == contract.HERE, "qualification_outside_phase")
        require(sha(qualification_path) == reviewed_sha, "reviewed_v2_bundle_changed")
        self.bundle, self.replayed = contract.build()
        require(self.bundle == read(qualification_path), "qualification_not_reproduced_from_retained_evidence")
        self.bundle_sha = reviewed_sha
        inventory = {pin: Path(path) for path, pin in self.bundle["input_pins"].items()}
        inventory[reviewed_sha] = qualification_path
        for path in (Path(__file__), contract.HERE / "run_staging_v2.py"):
            inventory[sha(path)] = path
        producers = {"qualification_rules": (Path(contract.__file__), sha(contract.__file__)),
            "history_parser": (old.PARSER, sha(old.PARSER)), "plugin": (guard.PLUGIN, guard.PLUGIN_SHA),
            "collector_primary": (contract.HERE / "capture.py", sha(contract.HERE / "capture.py"))}
        super().__init__(root, run_id, manifest_path=guard.MANIFEST, calendar_path=guard.CALENDAR,
            expected_manifest_sha256=old.MANIFEST_PIN, expected_calendar_sha256=old.CALENDAR_PIN,
            producer_files=producers, evidence_files=inventory)

    def _contract(self):
        entries, _ = super()._contract()
        return entries, {s["symbol"]: set(s["expected_price_dates"]) for s in self.bundle["scopes"]}

    def _qualifications(self, qualification):
        require(qualification == self.bundle_sha and self._evidence_json(qualification) == self.bundle, "v2_qualification_changed")
        require(self.bundle["staging_eligible"] is True and self.bundle["strict_pit"] is False and
                self.bundle["live_trading"] is False and self.bundle["production_promoted"] is False, "v2_scope_not_review_only")
        return {s["symbol"]: (s, old._hash_value(s)) for s in self.bundle["scopes"]}

    def records_from_evidence(self, qualification):
        self._verify_inputs(); self._qualifications(qualification)
        return [dict(row) for row in self.replayed]

    def _rows(self, records, approved):
        records = list(records)
        require(records == self.replayed and old._hash_value(records) == self.bundle["row_records_sha256"],
                "v2_rows_differ_from_verified_raw_replay")
        require({(r["symbol"], r["trade_date"]) for r in records} ==
                {(s, d) for s, dates in self.keys.items() for d in dates}, "v2_expected_keys_differ")
        return records

    def stage(self, records, qualifications):
        result = super().stage(records, qualifications)
        # No public pointer exists during this second, contract-specific transaction.
        try:
            for role, path in self.destinations.items():
                connection = self._open_write(path)
                try:
                    connection.executescript("""
                        CREATE TABLE dataset_contract (id INTEGER PRIMARY KEY CHECK(id=1), contract_json TEXT NOT NULL);
                        CREATE TABLE suspension_records (symbol TEXT NOT NULL, trade_date TEXT NOT NULL,
                            evidence_sha256 TEXT NOT NULL, record_json TEXT NOT NULL, PRIMARY KEY(symbol,trade_date));
                        CREATE TABLE coverage_inventory (symbol TEXT NOT NULL, trade_date TEXT NOT NULL,
                            classification TEXT NOT NULL CHECK(classification IN ('price','full_day_suspension')),
                            PRIMARY KEY(symbol,trade_date));
                        PRAGMA user_version=2;
                    """)
                    connection.execute("INSERT INTO dataset_contract VALUES (1,?)", (old._canonical(self.contract_record()),))
                    for gap in self.bundle["suspension_ledger"]:
                        connection.execute("INSERT INTO suspension_records VALUES (?,?,?,?)",
                            (gap["symbol"], gap["date"], old._hash_value(gap), old._canonical(gap)))
                        connection.execute("INSERT INTO coverage_inventory VALUES (?,?,?)", (gap["symbol"], gap["date"], "full_day_suspension"))
                    connection.executemany("INSERT INTO coverage_inventory VALUES (?,?,?)",
                        [(r["symbol"], r["trade_date"], "price") for r in self.replayed])
                    table = "daily_bar_cache" if role == "trading" else "daily_bars"
                    connection.execute(f"CREATE VIEW research_prices AS SELECT * FROM {table} WHERE trade_date BETWEEN '2023-09-04' AND '2026-09-04'")
                    connection.execute(f"CREATE VIEW warmup_prices AS SELECT * FROM {table} WHERE trade_date < '2023-09-04'")
                    connection.commit()
                finally:
                    connection.close()
            self._json_new(self.run_dir / "contract_v2.json", self.contract_record())
            self._verify_inputs()
            self._candidate = self.fingerprint()
            return {**result, "acceptance_contract": "real_session_v2", "candidate_fingerprint": self._candidate,
                "research_rows": self.bundle["research_rows"], "warmup_rows": self.bundle["warmup_rows"], "suspension_records": 298}
        except Exception:
            if not (self.run_dir / "FAILED.json").exists():
                self._json_new(self.run_dir / "FAILED.json", {"reason": "v2_contract_storage_failed", "published": False})
            raise

    def contract_record(self):
        return dict(schema="m2.real_session_contract.v2", authority_sha256=self.bundle["authority_sha256"],
            qualification_sha256=self.bundle_sha, producer_sha256=sha(__file__),
            research_start=old.RESEARCH_START, research_end=old.RESEARCH_END,
            expected_price_rows=self.bundle["rows_per_view"], expected_suspensions=298,
            listing_depth_shortfalls=self.bundle["listing_depth_shortfalls"],
            live_trading=False, production_promoted=False, strict_pit=False,
            original_contract_verdict="FAIL_preserved", source_totals_modified=False)

    def fingerprint(self):
        files = [*self.destinations.values(), self.run_dir / "candidate.json"]
        extra = self.run_dir / "contract_v2.json"
        if extra.exists():
            files.append(extra)
        for path in files:
            old._safe_existing_chain(path)
            require(path.is_file(), "v2_candidate_incomplete")
        return old._hash_value({p.name: sha(p) for p in files})

    def reconcile(self):
        """Read both real SQLite stores, compare all OHLCVA and full row lineage."""
        self._verify_inputs()
        require((self.run_dir / "contract_v2.json").is_file(), "v2_contract_metadata_missing")
        expected_prices = [(r["symbol"], r["trade_date"], *[r[f] for f in old.NUMBER_FIELDS], "none", old.SOURCE)
                           for r in self.replayed]
        expected_gaps = sorted((g["symbol"], g["date"], old._hash_value(g), old._canonical(g)) for g in self.bundle["suspension_ledger"])
        expected_inventory = sorted([(r["symbol"], r["trade_date"], "price") for r in self.replayed] +
            [(g["symbol"], g["date"], "full_day_suspension") for g in self.bundle["suspension_ledger"]])
        qualifications = self._qualifications(self.bundle_sha)
        shorts = {}
        for role, path in self.destinations.items():
            connection = sqlite3.connect("file:" + quote(path.as_posix(), safe="/:") + "?mode=ro", uri=True)
            try:
                connection.execute("PRAGMA query_only=ON")
                require(connection.execute("PRAGMA integrity_check").fetchall() == [("ok",)], "v2_sqlite_integrity_failed")
                require(connection.execute("PRAGMA foreign_key_check").fetchall() == [], "v2_sqlite_foreign_key_failed")
                table, source = ("daily_bar_cache", "source") if role == "trading" else ("daily_bars", "provider")
                actual = connection.execute(f"SELECT symbol,trade_date,open,high,low,close,volume,amount,adjustment_mode,{source} FROM {table} ORDER BY symbol,trade_date").fetchall()
                require(actual == expected_prices, "v2_stored_prices_or_amounts_differ_from_raw")
                require(connection.execute("SELECT symbol,trade_date,evidence_sha256,record_json FROM suspension_records ORDER BY symbol,trade_date").fetchall() == expected_gaps, "v2_suspension_evidence_changed")
                require(connection.execute("SELECT symbol,trade_date,classification FROM coverage_inventory ORDER BY symbol,trade_date").fetchall() == expected_inventory, "v2_coverage_inventory_changed")
                require(connection.execute("SELECT contract_json FROM dataset_contract").fetchall() == [(old._canonical(self.contract_record()),)], "v2_stored_contract_changed")
                require(connection.execute("SELECT COUNT(*) FROM research_prices").fetchone()[0] == self.bundle["research_rows"] and
                        connection.execute("SELECT COUNT(*) FROM warmup_prices").fetchone()[0] == self.bundle["warmup_rows"], "v2_view_counts_changed")
                short = {}
                for scope in self.bundle["scopes"]:
                    if scope["instrument_class"] == "stock":
                        count = connection.execute("SELECT COUNT(*) FROM warmup_prices WHERE symbol=?", (scope["symbol"],)).fetchone()[0]
                        if count < 250:
                            short[scope["symbol"]] = count
                require(short == contract.SHORT, "v2_actual_warmup_shortfalls_changed")
                shorts[role] = short
                if role == "trading":
                    expected_lineage = [(r["symbol"], r["trade_date"], r["raw_sha256"], r["request_sha256"], r["producer_sha256"],
                        r["parser_sha256"], r["capture_receipt_sha256"], r["capture_producer_manifest_sha256"], r["observed_at"],
                        r["point_index"], qualifications[r["symbol"]][1], r["source_name"], r["source_name_status"]) for r in self.replayed]
                    require(connection.execute("SELECT * FROM row_evidence ORDER BY symbol,trade_date").fetchall() == expected_lineage,
                            "v2_row_lineage_differ_from_raw")
                    expected_qual = sorted((s, pin, old._canonical(q)) for s, (q, pin) in qualifications.items())
                    require(connection.execute("SELECT * FROM qualification_records ORDER BY symbol").fetchall() == expected_qual, "v2_stored_qualification_changed")
                    require(connection.execute("SELECT COUNT(*) FROM daily_bar_cache WHERE quality_status != 'qualified_candidate'").fetchone()[0] == 0, "v2_invalid_quality_state")
                    units = connection.execute("SELECT DISTINCT symbol,volume_unit FROM daily_bar_cache ORDER BY symbol").fetchall()
                    require(units == sorted((s, q["volume_unit"]) for s, (q, _) in qualifications.items()), "v2_unit_declaration_changed")
            finally:
                connection.close()
        return dict(passed=True, rows_per_view=len(expected_prices), field_comparisons=len(expected_prices)*6*2,
            lineage_rows=len(expected_prices), suspended_dates=len(expected_gaps), coverage_keys=len(expected_inventory),
            listing_depth_shortfalls=shorts, unknown_gaps=0, extra_dates=0, duplicate_keys=0,
            source_values_modified=False, live_trading=False, strict_pit=False)

    def _gate_run(self, mode, revised, archives, baseline):
        gate, _ = old._legacy_modules()
        argv = ["validate", "--staging-trading", str(self.destinations["trading"]),
            "--staging-history", str(self.destinations["history"]), "--archive-trading", str(archives[0]),
            "--archive-history", str(archives[1]), "--pilot-manifest", str(self.manifest), "--calendar", str(self.calendar),
            "--baseline", str(baseline), "--history-scope", "all", "--pricing-basis", "none", "--history-basis", "none", "--transformation", "identity"]
        if mode == "warmup_collection":
            argv += ["--warmup-consumers", "both", "--warmup-start", contract.EARLY if revised else old.WARMUP_START,
                     "--warmup-sessions", "250", "--warmup-required"]
        original_eligibility, original_units = gate.entry_eligibility, gate.chk_units
        def eligibility(entry, window):
            # self.keys was independently replayed from calendar/listing/suspension facts.
            require(entry["symbol"] in self.keys, "v2_unplanned_gate_symbol")
            return sorted(set(window) & self.keys[entry["symbol"]]), "approved_real_session_v2"
        def units(connection, benchmarks=(), table="daily_bar_cache"):
            failures, count = [], 0
            for r in connection.execute(f"SELECT symbol,trade_date,low,high,volume,amount,volume_unit,adjustment_mode FROM {table}"):
                symbol, day, low, high, volume, amount, unit, basis = r
                if symbol in benchmarks:
                    continue
                count += 1
                try:
                    require(unit == "share" and basis == "none", "p4_unit_or_basis_invalid")
                    block = self.bundle["block_scope"] if (symbol, day) == ("BJ920006", "2023-12-04") else None
                    contract.p4_row(dict(symbol=symbol, trade_date=day, low=low, high=high, volume=volume, amount=amount), block)
                except (old.StagingError, ValueError, TypeError):
                    failures.append((symbol, day))
            return (gate.FAIL if failures or not count else gate.PASS, len(failures),
                f"contract=real_session_v2 stock_rows={count} failures={len(failures)}; original totals unchanged; one source-qualified block scope; same 2% bounds")
        output = io.StringIO()
        try:
            if revised:
                gate.entry_eligibility, gate.chk_units = eligibility, units
            with redirect_stdout(output), redirect_stderr(output):
                code = gate.main(argv)
        finally:
            gate.entry_eligibility, gate.chk_units = original_eligibility, original_units
        return code, output.getvalue()

    def validate(self, mode, *, archive_trading, archive_history, baseline):
        require(mode in old.MODES and mode not in self._receipts, "invalid_or_repeated_validation_mode")
        require(self._candidate is not None and not (self.run_dir / "FAILED.json").exists(), "candidate_not_staged")
        self._guard_paths()
        before, inputs = self.fingerprint(), self._verify_inputs()
        require(before == self._candidate, "candidate_changed_before_validation")
        archives = [Path(archive_trading).resolve(), Path(archive_history).resolve()]
        baseline = Path(baseline).resolve()
        require(archives == [guard.ARCHIVES["trading"].resolve(), guard.ARCHIVES["history"].resolve()] and baseline == guard.ARCHIVE_BASELINE.resolve(), "v2_validation_inputs_not_reviewed_archives")
        validation_inputs = tuple((str(p), sha(p)) for p in [*archives, baseline])
        reconciliation = self.reconcile()
        old_code, old_text = self._gate_run(mode, False, archives, baseline)
        require(old_code == 1, "original_contract_failure_not_observed")
        self._json_new(self.run_dir / (mode + "_original_gate.json"), dict(contract="original_unmodified", exit_code=old_code,
            gate_output=old_text, candidate_fingerprint=before, accepted=False))
        code, text = self._gate_run(mode, True, archives, baseline)
        statuses = check_gate_acceptance(text, code, mode, reconciliation["listing_depth_shortfalls"]["trading"])
        require(self.fingerprint() == before and self._verify_inputs() == inputs, "v2_candidate_or_inputs_changed_in_validation")
        require(all(sha(p) == pin for p, pin in validation_inputs), "v2_archive_changed")
        receipt = old.Receipt(mode, self.run_id, True, code, before, inputs, validation_inputs,
            "real_session_v2_integrity_pass; listing-depth shortfalls remain ineligible for 250-bar features")
        self._receipts[mode] = receipt
        path = self.run_dir / (mode + "_receipt.json")
        self._json_new(path, {**receipt.__dict__, "acceptance_contract": "real_session_v2", "gate_output": text,
            "gate_statuses": statuses, "raw_reconciliation": reconciliation,
            "original_gate_receipt_sha256": sha(self.run_dir / (mode + "_original_gate.json")),
            "live_trading": False, "production_promoted": False, "strict_pit": False})
        self._receipt_pins[mode] = sha(path)
        # Original failing gate artifacts are bound through each immutable receipt
        # and checked at publication; base input fingerprints stay fixed across modes.
        return receipt

    def publish(self, receipts):
        self.reconcile()
        for mode in old.MODES:
            receipt = read(self.run_dir / (mode + "_receipt.json"))
            require(receipt["acceptance_contract"] == "real_session_v2" and
                sha(self.run_dir / (mode + "_original_gate.json")) == receipt["original_gate_receipt_sha256"], "v1_failure_artifact_changed")
        return super().publish(receipts)
