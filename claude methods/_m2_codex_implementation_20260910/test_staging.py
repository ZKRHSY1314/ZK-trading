"""Offline adversarial tests; all source bodies and qualifications are synthetic.

Uses the unchanged 52-symbol manifest, calendar and M1 gates. No transport or
application startup is imported, and no production database is opened.
"""
from contextlib import redirect_stdout
from dataclasses import replace
from datetime import date, datetime, timedelta, timezone
import copy
import hashlib
import io
import json
from pathlib import Path
import shutil
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
import uuid

import staging as s


class StagingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="staging_test_inputs_", dir=s.HERE)
        cls.inputs = Path(cls.temp.name)
        cls.parent = s.ALLOWED_STAGING_PARENT
        cls.parent.mkdir(exist_ok=True)
        cls.roots = []
        cls.manifest = s.M1 / "pilot_symbols.csv"
        cls.calendar = s.PROJECT / "backend/.venv/Lib/site-packages/akshare/file_fold/calendar.json"
        cls.rules = cls.inputs / "synthetic_rules.py"
        cls.rules.write_text("# SYNTHETIC TEST ONLY: no qualification of actual data\n", encoding="utf-8")
        cls.collector = cls.inputs / "synthetic_collector.py"
        cls.collector.write_text("# Synthetic fixture producer; no transport\n", encoding="utf-8")
        cls.plugin = cls.inputs / "synthetic_plugin.bin"
        cls.plugin.write_bytes(b"synthetic plugin identity for isolated tests only")
        cls.producers = {"qualification_rules": (cls.rules, s._sha(cls.rules)),
                         "history_parser": (s.PARSER, s._sha(s.PARSER)),
                         "plugin": (cls.plugin, s._sha(cls.plugin)),
                         "collector_fixture": (cls.collector, s._sha(cls.collector))}
        cls.evidence = {}

        def retain(name, value):
            path = cls.inputs / name
            path.write_text(s._canonical(value), encoding="utf-8")
            digest = s._sha(path)
            cls.evidence[digest] = path
            return digest
        cls.retain = staticmethod(retain)
        producer_manifest = retain("producer_pins.json", {str(cls.collector): s._sha(cls.collector)})
        reference = retain("synthetic_evidence.json", {"evidence_mode": "synthetic_test_only", "actual_data_qualified": False})
        initial = cls.new_run("fixture_definition")
        parser = s._history_parser()
        observed = datetime.now(timezone.utc).isoformat()
        reserved = (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()
        scopes = []
        for symbol in initial.entries:
            benchmark = symbol in s.BENCHMARKS
            if benchmark:
                native, public = s.BENCHMARKS[symbol]
                spec = parser.SecuritySpec.benchmark(symbol, host_full_code=native,
                    response_full_code=public, mapping_evidence="synthetic_test_only")
            else:
                spec = parser.SecuritySpec.stock(symbol)
            request = parser.build_history_request(spec, s.WARMUP_START, s.RESEARCH_END)
            # Existing actual captures used hostFullCode without a redundant market.
            request["security"] = {"hostFullCode": spec.host_full_code}
            identity = {"market": 1, "code": spec.response_code, "fullCode": spec.response_full_code,
                        "hostMarketCode": spec.host_market_code, "hostFullCode": spec.host_full_code, "name": ""}
            points = []
            for day in sorted(initial.keys[symbol]):
                points.append({"timestampUtc": day + "T07:00:00Z", "values": {
                    "full_code": spec.response_full_code, "security_name": "\uf8f5",
                    "date_time": int(day.replace("-", "")), "open": 10, "high": 11,
                    "low": 9, "latest": 10, "transaction_volume": 1000,
                    "transaction_amount": None if benchmark else 10000}})
            raw_sha = retain(symbol + "_raw.json", {"ok": True, "data": {"items": [{"security": identity, "points": points}]}})
            receipt = {"job": {"id": len(scopes) + 1, "symbol": symbol, "host_full_code": spec.host_full_code,
                               "payload": request}, "http_status": 200, "raw_sha256": raw_sha,
                       "raw_bytes": cls.evidence[raw_sha].stat().st_size, "source_security": identity,
                       "reserved_at": reserved, "observed_at": observed, "stop_reason": None}
            receipt_sha = retain(symbol + "_receipt.json", receipt)
            scopes.append({"symbol": symbol, "instrument_class": "benchmark" if benchmark else "stock",
                "raw_body_sha256": raw_sha, "request_sha256": s._hash_value(request),
                "capture_receipt_sha256": receipt_sha, "capture_producer_manifest_sha256": producer_manifest,
                "collector_sha256": s._sha(cls.collector), "start_date": s.WARMUP_START, "end_date": s.RESEARCH_END,
                "period": 7, "adjustment": 0, "plugin_sha256": s._sha(cls.plugin), "rules_sha256": s._sha(cls.rules),
                "vendor_basis_status": "verified", "unit_status": "not_applicable" if benchmark else "verified",
                "identity_status": "verified",
                "vendor_basis": "unadjusted", "volume_unit": "not_applicable" if benchmark else "share",
                "amount_unit": "not_applicable" if benchmark else "CNY", "evidence_sha256": [reference]})
        cls.bundle = {"schema": "m2.ths.qualification_evidence.v1", "rules_sha256": s._sha(cls.rules),
                      "evidence_mode": "synthetic_test_only", "scopes": scopes}
        cls.bundle_sha = retain("qualifications.json", cls.bundle)
        cls.archives = [cls.inputs / "archive_trading.sqlite3", cls.inputs / "archive_history.sqlite3"]
        for path in cls.archives:
            conn = sqlite3.connect(path)
            conn.execute("CREATE TABLE preserved_archive (id INTEGER PRIMARY KEY, value TEXT)")
            conn.execute("INSERT INTO preserved_archive VALUES (1, 'untouched fixture')")
            conn.commit()
            conn.close()
        cls.baseline = cls.inputs / "archive_baseline.json"
        gate, _ = s._legacy_modules()
        with redirect_stdout(io.StringIO()):
            code = gate.main(["snapshot", "--archive-trading", str(cls.archives[0]),
                "--archive-history", str(cls.archives[1]), "--calendar", str(cls.calendar),
                "--baseline-out", str(cls.baseline)])
        if code != 0:
            raise RuntimeError("synthetic archive baseline failed")
        cls.preserved = {path: s._sha(path) for path in [*cls.archives, cls.baseline, cls.manifest, cls.calendar, *s.LEGACY_FILES]}

    @classmethod
    def tearDownClass(cls):
        for path, digest in cls.preserved.items():
            if s._sha(path) != digest:
                raise AssertionError("protected test input changed: " + str(path))
        for root in cls.roots:
            # Recursive cleanup is confined to this test's explicitly created roots.
            if root.exists():
                if root.resolve().parent != cls.parent.resolve() or not root.name.startswith("synthetic_test_"):
                    raise RuntimeError("unsafe test cleanup target")
                shutil.rmtree(root)
        if cls.inputs.resolve().parent != s.HERE.resolve() or not cls.inputs.name.startswith("staging_test_inputs_"):
            raise RuntimeError("unsafe fixture cleanup target")
        cls.temp.cleanup()

    @classmethod
    def new_run(cls, name, **overrides):
        root = cls.parent / ("synthetic_test_" + uuid.uuid4().hex)
        cls.roots.append(root)
        arguments = {"manifest_path": cls.manifest, "calendar_path": cls.calendar,
            "expected_manifest_sha256": s.MANIFEST_PIN, "expected_calendar_sha256": s.CALENDAR_PIN,
            "producer_files": cls.producers, "evidence_files": cls.evidence,
            "evidence_mode": "synthetic_test_only"}
        arguments.update(overrides)
        return s.StagingRun(root, name, **arguments)

    def stage(self, run=None):
        run = run or self.new_run("candidate")
        result = run.stage_from_evidence(self.bundle_sha)
        self.assertEqual(result["rows_per_view"], 45935)
        return run

    def validate(self, run):
        return [run.validate(mode, archive_trading=self.archives[0], archive_history=self.archives[1],
                             baseline=self.baseline) for mode in s.MODES]

    def mutate_bundle(self, mutate):
        bundle = copy.deepcopy(self.bundle)
        mutate(bundle)
        return self.retain("altered_" + uuid.uuid4().hex + ".json", bundle)

    def test_full_corpus_real_gates_and_atomic_staging_publication(self):
        run = self.stage()
        before = {path: s._sha(path) for path in run.destinations.values()}
        receipts = self.validate(run)
        self.assertTrue(all(receipt.accepted for receipt in receipts), [r.reason for r in receipts])
        self.assertEqual([receipt.gate_exit for receipt in receipts], [0, 1])
        for path, table in ((run.destinations["trading"], "daily_bar_cache"), (run.destinations["history"], "daily_bars")):
            with sqlite3.connect("file:" + path.as_posix() + "?mode=ro", uri=True) as conn:
                self.assertEqual(conn.execute("SELECT COUNT(*) FROM " + table).fetchone()[0], 45935)
        with sqlite3.connect("file:" + run.destinations["trading"].as_posix() + "?mode=ro", uri=True) as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM row_evidence WHERE source_name IS NULL AND source_name_status='invalid_source_name'").fetchone()[0], 45935)
            self.assertEqual(conn.execute("SELECT COUNT(DISTINCT symbol) FROM qualification_records").fetchone()[0], 52)
        result = run.publish(receipts)
        self.assertTrue(result["published"])
        pointer = json.loads(run.pointer.read_bytes())
        self.assertEqual(pointer["evidence_mode"], "synthetic_test_only")
        self.assertFalse(pointer["production_promoted"])
        self.assertFalse(pointer["live_trading"])
        self.assertEqual(before, {path: s._sha(path) for path in run.destinations.values()})

    def test_arbitrary_dict_qualification_is_rejected_before_writes(self):
        run = self.new_run("dict_qualification")
        with self.assertRaisesRegex(s.StagingError, "evidence_reference_missing"):
            run.stage([], {"verified": True})
        self.assertFalse(run.root.exists())

    def test_unverified_and_wrongly_scoped_qualifications_fail_closed(self):
        variants = [lambda b: b["scopes"][0].__setitem__("unit_status", "unknown"),
                    lambda b: b["scopes"][0].__setitem__("identity_status", "failed"),
                    lambda b: b["scopes"][0].__setitem__("vendor_basis_status", "unknown"),
                    lambda b: b["scopes"][0].__setitem__("rules_sha256", "a" * 64),
                    lambda b: b["scopes"][0].__setitem__("start_date", "2023-09-04"),
                    lambda b: b["scopes"][0].__setitem__("adjustment", True),
                    lambda b: b["scopes"].pop(),
                    lambda b: b.__setitem__("evidence_mode", "retained_market_capture")]
        for mutate in variants:
            digest = self.mutate_bundle(mutate)
            run = self.new_run("bad_qualification")
            with self.assertRaises(s.StagingError):
                run.stage_from_evidence(digest)
            self.assertFalse(run.root.exists())

    def test_only_frozen_benchmarks_can_use_unit_not_applicable(self):
        run = self.new_run("benchmark_unit_routing")
        approved = run._qualifications(self.bundle_sha)
        self.assertEqual({symbol for symbol, (scope, _) in approved.items()
                          if scope["unit_status"] == "not_applicable"}, set(s.BENCHMARKS))
        stock_index = next(i for i, scope in enumerate(self.bundle["scopes"])
                           if scope["instrument_class"] == "stock")
        benchmark_index = next(i for i, scope in enumerate(self.bundle["scopes"])
                               if scope["instrument_class"] == "benchmark")
        variants = [
            (stock_index, {"unit_status": "not_applicable"}),
            (stock_index, {"instrument_class": "benchmark", "unit_status": "not_applicable",
                           "volume_unit": "not_applicable", "amount_unit": "not_applicable"}),
            (benchmark_index, {"instrument_class": "stock", "unit_status": "verified",
                               "volume_unit": "share", "amount_unit": "CNY"}),
            (benchmark_index, {"unit_status": "verified"}),
            (benchmark_index, {"volume_unit": "unknown"}),
            (benchmark_index, {"amount_unit": "CNY"}),
            (benchmark_index, {"vendor_basis_status": "unknown"}),
            (benchmark_index, {"identity_status": "unknown"}),
        ]
        for index, updates in variants:
            digest = self.mutate_bundle(lambda bundle: bundle["scopes"][index].update(updates))
            denied = self.new_run("invalid_unit_applicability")
            with self.assertRaises(s.StagingError):
                denied._qualifications(digest)
            self.assertFalse(denied.root.exists())

    def test_raw_point_value_date_and_identity_cannot_be_forged(self):
        for field, value in (("close", 10.5), ("point_index", 1), ("symbol", "SH999999"),
                             ("producer_sha256", "a" * 64), ("request_sha256", "b" * 64),
                             ("observed_at", "2026-09-05T12:00:00+00:00")):
            run = self.new_run("forged_row")
            records = run.records_from_evidence(self.bundle_sha)
            records[0][field] = value
            with self.assertRaises(s.StagingError):
                run.stage(records, self.bundle_sha)
            self.assertFalse(run.root.exists())

    def test_raw_scope_and_request_substitution_rejected(self):
        digest = self.mutate_bundle(lambda b: b["scopes"][0].__setitem__("raw_body_sha256", b["scopes"][1]["raw_body_sha256"]))
        run = self.new_run("raw_substitution")
        with self.assertRaisesRegex(s.StagingError, "capture_body_scope_mismatch"):
            run.stage_from_evidence(digest)
        digest = self.mutate_bundle(lambda b: b["scopes"][0].__setitem__("request_sha256", "0" * 64))
        run = self.new_run("request_substitution")
        with self.assertRaisesRegex(s.StagingError, "capture_request_scope_mismatch"):
            run.stage_from_evidence(digest)

    def test_duplicate_and_missing_keys_rejected_without_databases(self):
        for variant in ("duplicate", "missing"):
            run = self.new_run("bad_inventory")
            records = run.records_from_evidence(self.bundle_sha)
            if variant == "duplicate":
                records.append(dict(records[0]))
            else:
                records.pop()
            with self.assertRaisesRegex(s.StagingError, "duplicate_business_key|pilot_key_inventory_incomplete"):
                run.stage(records, self.bundle_sha)
            self.assertFalse(run.root.exists())

    def test_forged_receipts_and_missing_mode_cannot_publish(self):
        run = self.stage()
        receipts = self.validate(run)
        with self.assertRaisesRegex(s.StagingError, "receipt_not_issued_by_this_run"):
            run.publish([replace(receipts[0]), receipts[1]])
        with self.assertRaisesRegex(s.StagingError, "two_receipts_required"):
            run.publish(receipts[:1])
        self.assertFalse(run.pointer.exists())

    def test_real_gate_rejects_false_unit_qualification(self):
        # A fabricated qualification cannot make the unchanged M1 P4 arithmetic
        # agree with raw data. Retain the contradictory body, then run real gates.
        bundle = copy.deepcopy(self.bundle)
        scope = next(item for item in bundle["scopes"] if item["symbol"] not in s.BENCHMARKS)
        raw = json.loads(self.evidence[scope["raw_body_sha256"]].read_bytes())
        raw["data"]["items"][0]["points"][0]["values"]["transaction_amount"] = 100000
        raw_sha = self.retain("contradictory_units_raw.json", raw)
        receipt = json.loads(self.evidence[scope["capture_receipt_sha256"]].read_bytes())
        receipt.update(raw_sha256=raw_sha, raw_bytes=self.evidence[raw_sha].stat().st_size)
        scope.update(raw_body_sha256=raw_sha, capture_receipt_sha256=self.retain("contradictory_units_receipt.json", receipt))
        digest = self.retain("contradictory_units_qualification.json", bundle)
        run = self.new_run("unit_failure")
        run.stage_from_evidence(digest)
        receipts = self.validate(run)
        self.assertFalse(any(receipt.accepted for receipt in receipts))
        research = json.loads((run.run_dir / "research_receipt.json").read_bytes())
        self.assertIn("P4", research["gate_output"])
        self.assertIn("contradicted=1", research["gate_output"])
        with self.assertRaisesRegex(s.StagingError, "receipt_binding_or_acceptance_failed"):
            run.publish(receipts)
        self.assertFalse(run.pointer.exists())

    def test_cross_run_receipt_and_archive_alias_rejected(self):
        run = self.stage()
        receipts = self.validate(run)
        other = self.stage(self.new_run("other_candidate"))
        with self.assertRaisesRegex(s.StagingError, "receipt_not_issued_by_this_run"):
            other.publish(receipts)
        with self.assertRaisesRegex(s.StagingError, "archive_views_alias"):
            other.validate("research", archive_trading=self.archives[0], archive_history=self.archives[0], baseline=self.baseline)

    def test_capture_window_duplicate_identifiers_and_collector_manifest_rejected(self):
        for variant in ("window", "identifiers", "collector_manifest"):
            bundle = copy.deepcopy(self.bundle)
            scope = bundle["scopes"][0]
            receipt = json.loads(self.evidence[scope["capture_receipt_sha256"]].read_bytes())
            request = receipt["job"]["payload"]
            if variant == "window":
                request["startTimeUtc"] = "2023-09-03T16:00:00Z"
            elif variant == "identifiers":
                request["security"]["code"] = scope["symbol"][2:]
            else:
                scope["capture_producer_manifest_sha256"] = self.retain("wrong_collector_manifest.json", {str(self.collector): "f" * 64})
            scope["request_sha256"] = s._hash_value(request)
            scope["capture_receipt_sha256"] = self.retain(variant + "_altered_receipt.json", receipt)
            digest = self.retain(variant + "_altered_scope.json", bundle)
            run = self.new_run("invalid_capture")
            with self.assertRaises(s.StagingError):
                run.stage_from_evidence(digest)
            self.assertFalse(run.root.exists())

    def test_candidate_mutation_and_receipt_artifact_tampering_block_publication(self):
        run = self.stage()
        receipts = self.validate(run)
        path = run.run_dir / "research_receipt.json"
        original = path.read_bytes()
        path.write_bytes(original + b" ")
        with self.assertRaisesRegex(s.StagingError, "receipt_artifact_changed"):
            run.publish(receipts)
        path.write_bytes(original)
        with sqlite3.connect(run.destinations["history"]) as conn:
            conn.execute("DELETE FROM daily_bars WHERE rowid=(SELECT MIN(rowid) FROM daily_bars)")
        with self.assertRaisesRegex(s.StagingError, "candidate_changed_before_publication"):
            run.publish(receipts)
        self.assertFalse(run.pointer.exists())

    def test_pointer_failure_keeps_previous_and_cleans_only_owned_tmp(self):
        run = self.stage()
        receipts = self.validate(run)
        previous = {"schema": "m2.ths.staging_pointer.v1", "evidence_mode": "synthetic_test_only",
                    "run_id": "prior_fixture", "live_trading": False, "production_promoted": False}
        run.pointer.write_text(s._canonical(previous), encoding="utf-8")
        original = run.pointer.read_bytes()
        with patch.object(s.os, "replace", side_effect=OSError("simulated atomic replace failure")):
            with self.assertRaises(OSError):
                run.publish(receipts)
        self.assertEqual(run.pointer.read_bytes(), original)
        self.assertFalse(run.pointer_tmp.exists())
        self.assertTrue(all(path.exists() for path in run.destinations.values()))

    def test_unapproved_root_reduced_contract_and_actual_mode_cannot_use_fixtures(self):
        for options in ({"expected_manifest_sha256": "0" * 64}, {"evidence_mode": "actual"}):
            with self.assertRaises(s.StagingError):
                self.new_run("bad_contract", **options)
        run = self.new_run("fixture_in_actual_mode", evidence_mode="retained_market_capture")
        with self.assertRaisesRegex(s.StagingError, "qualification_mode_mismatch"):
            run.stage_from_evidence(self.bundle_sha)
        with self.assertRaisesRegex(s.StagingError, "staging_root_outside_allowlist"):
            s.StagingRun(self.inputs / "synthetic_test_bad", "outside", manifest_path=self.manifest,
                calendar_path=self.calendar, expected_manifest_sha256=s.MANIFEST_PIN,
                expected_calendar_sha256=s.CALENDAR_PIN, producer_files=self.producers,
                evidence_files=self.evidence, evidence_mode="synthetic_test_only")

    def test_input_change_after_staging_is_detected(self):
        run = self.stage()
        raw_path = self.evidence[self.bundle["scopes"][0]["raw_body_sha256"]]
        original = raw_path.read_bytes()
        try:
            raw_path.write_bytes(original + b" ")
            with self.assertRaisesRegex(s.StagingError, "input_pin_mismatch"):
                self.validate(run)
        finally:
            raw_path.write_bytes(original)
        self.assertFalse(run.pointer.exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
