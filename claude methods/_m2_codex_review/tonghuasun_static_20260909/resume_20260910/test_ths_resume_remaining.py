"""Offline continuation tests. All capture, endpoint and credential I/O is mocked."""
from __future__ import annotations

from contextlib import ExitStack, redirect_stdout
from copy import deepcopy
from datetime import datetime, timezone
import importlib.util
import io
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch


HERE = Path(__file__).resolve().parent
with ExitStack() as import_guard:
    for target in ("socket.socket", "http.client.HTTPConnection", "subprocess.run"):
        import_guard.enter_context(patch(target, side_effect=AssertionError("real external operation forbidden")))
    spec = importlib.util.spec_from_file_location("remaining_probe_under_test", HERE / "ths_resume_remaining.py")
    resume = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(resume)

REAL_PREFLIGHT = resume.preflight
REAL_VERIFY_PRIOR = resume.verify_prior
DAYS = ["2023-08-31", "2023-09-01", "2023-09-04"]
EXPECTED = {"listing": "2002-01-01", "benchmark": False, "warmup": DAYS[:2], "research": DAYS[2:]}


def response_for(job, *, full_code=None):
    code = job["payload"]["security"]["fullCode"] if full_code is None else full_code
    data = {"ok": True, "data": {"adjustment": 0, "items": [{
        "security": {"fullCode": code},
        "points": [{"timestampUtc": day + "T00:00:00Z", "values": {
            "full_code": code, "date_time": day, "open": "10", "high": "12", "low": "9",
            "latest": "11", "transaction_volume": "1000", "transaction_amount": "11000",
        }} for day in DAYS],
    }]}}
    return json.dumps(data).encode("utf-8")


class MemoryPath:
    def __init__(self, name, storage):
        self.name, self.storage = name, storage

    def __str__(self):
        return self.name

    def __truediv__(self, child):
        return MemoryPath(self.name + "/" + str(child), self.storage)

    def exists(self):
        return self.name in self.storage

    def mkdir(self, *, exist_ok):
        if self.exists():
            raise FileExistsError(self.name)
        self.storage[self.name] = "directory"

    def write_bytes(self, data):
        self.storage[self.name] = bytes(data)
        return len(data)


class RemainingProbeTests(unittest.TestCase):
    def setUp(self):
        self.protection = ExitStack()
        self.addCleanup(self.protection.close)
        for target in ("socket.socket", "http.client.HTTPConnection", "subprocess.run", "builtins.open"):
            self.protection.enter_context(patch(target, side_effect=AssertionError("real external operation forbidden")))
        self.protection.enter_context(patch.object(Path, "open", side_effect=AssertionError("real file operation forbidden")))

    def capture_mocks(self, *, existing=False, fetch_effect=None):
        storage = {}
        live = MemoryPath("in-memory-continuation", storage)
        if existing:
            storage[str(live)] = "existing claim"

        def write(path, data, *, exclusive=False):
            name = str(path)
            if exclusive and name in storage:
                raise FileExistsError(name)
            storage[name] = deepcopy(data)

        stack = ExitStack()
        self.addCleanup(stack.close)
        stack.enter_context(patch.object(resume, "LIVE", live))
        stack.enter_context(patch.object(resume.base, "write_json", side_effect=write))
        prior = stack.enter_context(patch.object(resume, "verify_prior", return_value={"prior_attempts_consumed": 1}))
        expected = stack.enter_context(patch.object(resume.base, "expected_keys", return_value={
            symbol: deepcopy(EXPECTED) for symbol in resume.base.SYMBOLS}))
        preflight = stack.enter_context(patch.object(resume, "preflight", return_value={"passed": True, "synthetic": True}))
        credentials = stack.enter_context(patch.object(resume.base, "local_credentials", return_value="a" * 64))
        fetch = stack.enter_context(patch.object(resume, "fetch_remaining", side_effect=(
            (lambda job, token: (200, response_for(job))) if fetch_effect is None else fetch_effect)))
        stack.enter_context(patch.object(resume, "digest", return_value="synthetic pin"))
        stack.enter_context(patch.object(resume.time, "monotonic", return_value=0.0))
        stack.enter_context(patch.object(resume.time, "sleep"))
        stack.enter_context(redirect_stdout(io.StringIO()))
        return SimpleNamespace(storage=storage, live=live, prior=prior, expected=expected,
            preflight=preflight, credentials=credentials, fetch=fetch)

    def test_plan_contains_only_original_jobs_two_through_six(self):
        jobs = resume.remaining_jobs()
        self.assertEqual(jobs, resume.base.fixed_jobs()[1:])
        self.assertEqual([job["id"] for job in jobs], [2, 3, 4, 5, 6])
        self.assertEqual([(j["symbol"], j["mode"]) for j in jobs], [
            ("SH600011", "range"), ("BJ920000", "count"), ("BJ920000", "range"),
            ("SH000300", "count"), ("SH000300", "range")])
        plan = resume.continuation_plan()
        self.assertEqual((plan["prior_attempts_consumed"], plan["max_new_attempts"], plan["max_cumulative_attempts"]), (1, 5, 6))
        self.assertIs(plan["repeat_job_1"], False)
        self.assertEqual(plan["retries"], 0)
        for flag in ("database_access", "production_writes", "live_trading", "eligible"):
            self.assertIs(plan[flag], False)

    def test_original_job_one_is_rejected_before_transport(self):
        with patch.object(resume.base, "fetch") as fetch:
            with self.assertRaisesRegex(resume.base.StopProbe, "^request_not_in_remaining_plan$"):
                resume.fetch_remaining(resume.base.fixed_jobs()[0], "synthetic-unused-token")
            fetch.assert_not_called()

    def test_boolean_payload_cannot_bypass_remaining_plan(self):
        for field, value in (("market", True), ("adjustment", False)):
            job = deepcopy(resume.remaining_jobs()[0])
            job["payload"][field] = value
            with self.subTest(field=field), patch.object(resume.base, "fetch") as fetch:
                with self.assertRaisesRegex(resume.base.StopProbe, "^request_not_in_remaining_plan$"):
                    resume.fetch_remaining(job, "synthetic-unused-token")
                fetch.assert_not_called()

    def test_valid_remaining_job_uses_frozen_transport_once(self):
        job = resume.remaining_jobs()[0]
        with patch.object(resume.base, "fetch", return_value=(200, b"synthetic bytes")) as fetch:
            self.assertEqual(resume.fetch_remaining(job, "synthetic-token"), (200, b"synthetic bytes"))
            fetch.assert_called_once_with(job, "synthetic-token")

    def test_five_new_attempts_produce_cumulative_six_and_no_job_one(self):
        mocks = self.capture_mocks()
        self.assertEqual(resume.capture(), 0)
        self.assertEqual([call.args[0]["id"] for call in mocks.fetch.call_args_list], [2, 3, 4, 5, 6])
        summary = mocks.storage[str(mocks.live / "summary.json")]
        self.assertEqual((summary["prior_rest_attempts"], summary["new_rest_attempts"], summary["cumulative_rest_attempts"]), (1, 5, 6))
        self.assertEqual(summary["rest_attempts_not_issued"], 0)
        self.assertIs(summary["job_1_reissued"], False)
        self.assertIs(summary["automatic_resume_allowed"], False)
        self.assertIs(summary["m2_accepted"], False)
        self.assertIs(summary["eligible"], False)
        self.assertNotIn(str(mocks.live / "attempt_1.json"), mocks.storage)
        self.assertEqual([mocks.storage[str(mocks.live / f"attempt_{i}.json")]["cumulative_attempt_number"] for i in range(2, 7)], [2, 3, 4, 5, 6])

    def test_successful_range_does_not_fabricate_sh600011_count_pair(self):
        mocks = self.capture_mocks()
        self.assertEqual(resume.capture(), 0)
        summary = mocks.storage[str(mocks.live / "summary.json")]
        self.assertEqual(set(summary["pairs"]), {"BJ920000", "SH000300"})
        self.assertNotIn("SH600011", summary["pairs"])
        self.assertEqual(summary["SH600011_count"], "original HTTP401; no successful count observation")

    def test_http_failure_stops_immediately_without_retry(self):
        for status in (401, 302, 503):
            with self.subTest(status=status):
                mocks = self.capture_mocks(fetch_effect=lambda job, token: (status, b"synthetic failure"))
                self.assertEqual(resume.capture(), 1)
                self.assertEqual(mocks.fetch.call_count, 1)
                summary = mocks.storage[str(mocks.live / "summary.json")]
                self.assertEqual(summary["stop_reason"], f"http_status_{status}_stop_no_retry")
                self.assertEqual((summary["new_rest_attempts"], summary["cumulative_rest_attempts"], summary["rest_attempts_not_issued"]), (1, 2, 4))

    def test_transport_failure_has_reserved_attempt_and_stops(self):
        holder = {}

        def fail(job, token):
            mocks = holder["mocks"]
            receipt = mocks.storage[str(mocks.live / "attempt_2.json")]
            self.assertEqual(receipt["state"], "reserved_before_network")
            self.assertEqual(receipt["cumulative_attempt_number"], 2)
            raise OSError("synthetic timeout")

        mocks = self.capture_mocks(fetch_effect=fail)
        holder["mocks"] = mocks
        self.assertEqual(resume.capture(), 1)
        self.assertEqual(mocks.fetch.call_count, 1)
        self.assertEqual(mocks.storage[str(mocks.live / "summary.json")]["stop_reason"], "transport_failed_or_timed_out_no_retry")

    def test_response_identity_failure_stops_before_next_job(self):
        mocks = self.capture_mocks(fetch_effect=lambda job, token: (200, response_for(job, full_code="000300.SZ")))
        self.assertEqual(resume.capture(), 1)
        self.assertEqual(mocks.fetch.call_count, 1)
        self.assertEqual(mocks.storage[str(mocks.live / "summary.json")]["stop_reason"], "response_contract_failure")

    def test_existing_claim_blocks_credentials_and_transport(self):
        mocks = self.capture_mocks(existing=True)
        with self.assertRaisesRegex(resume.base.StopProbe, "^continuation_already_claimed$"):
            resume.capture()
        mocks.credentials.assert_not_called()
        mocks.fetch.assert_not_called()

    def test_preflight_failure_occurs_before_credentials(self):
        mocks = self.capture_mocks()
        mocks.preflight.side_effect = resume.base.StopProbe("runtime_inventory_failed")
        with self.assertRaisesRegex(resume.base.StopProbe, "^runtime_inventory_failed$"):
            resume.capture()
        mocks.credentials.assert_not_called()
        mocks.fetch.assert_not_called()
        self.assertEqual(mocks.storage, {})

    def test_actual_endpoint_guard_failure_occurs_before_credentials(self):
        mocks = self.capture_mocks()
        endpoint = {"baseUrl": "http://127.0.0.1:17180", "port": 17180,
            "processId": 23512, "startedAtUtc": "2026-09-09T16:09:03Z",
            "listenAddresses": ["127.0.0.1"], "lanBaseUrls": []}
        result = {"passed": True, "host_process": {"pid": 25912, "started_utc": "2026-09-09T16:08:53Z"}}
        launch = {"context": {"host_process_id": 25912}}

        def read_bytes(path):
            if path.name == "client_launch_receipt.json":
                return json.dumps(launch).encode()
            if path.name == "endpoint.json":
                return json.dumps(endpoint).encode()
            raise AssertionError("unexpected synthetic file read")

        with patch.object(resume, "preflight", side_effect=REAL_PREFLIGHT), \
             patch.object(Path, "read_text", return_value="# synthetic preflight; never executed"), \
             patch.object(Path, "read_bytes", read_bytes), \
             patch.object(Path, "stat", return_value=SimpleNamespace(st_mtime=datetime(2026, 9, 9, 16, 9, 4, tzinfo=timezone.utc).timestamp())), \
             patch.object(resume.subprocess, "run", return_value=SimpleNamespace(returncode=0, stdout=json.dumps(result))):
            with self.assertRaisesRegex(resume.base.StopProbe, "^project_endpoint_identity_or_freshness_failed$"):
                resume.capture()
        mocks.credentials.assert_not_called()
        mocks.fetch.assert_not_called()
        self.assertEqual(mocks.storage, {})

    def test_old_manifest_pin_failure_occurs_before_credentials_or_preflight(self):
        mocks = self.capture_mocks()
        with patch.object(resume, "verify_prior", side_effect=REAL_VERIFY_PRIOR), \
             patch.object(resume, "digest", return_value="wrong manifest hash"):
            with self.assertRaisesRegex(resume.base.StopProbe, "^old_delivery_manifest_changed$"):
                resume.capture()
        mocks.preflight.assert_not_called()
        mocks.credentials.assert_not_called()
        mocks.fetch.assert_not_called()
        self.assertEqual(mocks.storage, {})

    def test_old_artifact_change_occurs_before_credentials_or_preflight(self):
        mocks = self.capture_mocks()
        manifest = {"artifacts": {"synthetic_evidence.bin": "expected synthetic evidence hash"}}

        def digest(path):
            if path.name == "probe_delivery_manifest.json":
                return resume.PINS["probe_delivery_manifest.json"]
            if path.name == "synthetic_evidence.bin":
                return "changed synthetic evidence hash"
            raise AssertionError("unexpected synthetic digest")

        with patch.object(resume, "verify_prior", side_effect=REAL_VERIFY_PRIOR), \
             patch.object(resume, "digest", side_effect=digest), \
             patch.object(Path, "read_bytes", return_value=json.dumps(manifest).encode()):
            with self.assertRaisesRegex(resume.base.StopProbe, "^old_evidence_changed$"):
                resume.capture()
        mocks.preflight.assert_not_called()
        mocks.credentials.assert_not_called()
        mocks.fetch.assert_not_called()
        self.assertEqual(mocks.storage, {})


if __name__ == "__main__":
    unittest.main(verbosity=2)
