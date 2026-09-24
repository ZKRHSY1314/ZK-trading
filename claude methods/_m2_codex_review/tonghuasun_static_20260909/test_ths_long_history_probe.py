"""Synthetic, network-blocked tests for the isolated six-request probe.

Run directly with backend/.venv/Scripts/python.exe -B; no project imports,
credentials, calendar/manifest reads, database access, or real capture writes.
"""
from __future__ import annotations

from contextlib import ExitStack, redirect_stdout
from copy import deepcopy
from datetime import date, timedelta
import importlib.util
import io
import json
from pathlib import Path
import unittest
from unittest.mock import Mock, patch


HERE = Path(__file__).resolve().parent
with ExitStack() as import_guard:
    import_guard.enter_context(patch("socket.socket", side_effect=AssertionError("real socket forbidden")))
    import_guard.enter_context(patch("http.client.HTTPConnection", side_effect=AssertionError("real HTTP forbidden")))
    import_guard.enter_context(patch("subprocess.run", side_effect=AssertionError("subprocess forbidden")))
    spec = importlib.util.spec_from_file_location("ths_probe_under_test", HERE / "ths_long_history_probe.py")
    probe = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(probe)


def synthetic_dates(count=978):
    """Explicit synthetic weekdays; these are not claims about trading days."""
    current = date.fromisoformat(probe.START)
    result = []
    while len(result) < count:
        if current.weekday() < 5:
            result.append(current.isoformat())
        current += timedelta(days=1)
    assert result[-1] <= probe.END
    return result


DAYS = synthetic_dates()
EXPECTED = {
    "listing": "2002-01-01", "benchmark": False,
    "research": [day for day in DAYS if day >= "2023-09-04"],
    "warmup": [day for day in DAYS if day <= "2023-09-01"],
}


def envelope(days=DAYS, full_code="600011.SH"):
    return {"ok": True, "data": {"adjustment": 0, "items": [{
        "security": {"fullCode": full_code},
        "points": [{"timestampUtc": day + "T00:00:00Z", "values": {
            "full_code": full_code, "date_time": day,
            "open": "10.00", "high": "12", "low": "9.0", "latest": "11.00",
            "transaction_volume": "1000", "transaction_amount": "11000.00",
        }} for day in days],
    }]}}


def raw(data):
    return json.dumps(data, ensure_ascii=False).encode("utf-8")


class MemoryPath:
    """Minimal in-memory path for capture; never creates a filesystem entry."""
    def __init__(self, name, storage):
        self.name, self.storage = name, storage

    def __str__(self):
        return self.name

    def __truediv__(self, child):
        return MemoryPath(self.name + "/" + str(child), self.storage)

    def mkdir(self, *, exist_ok):
        if self.name in self.storage:
            raise FileExistsError(self.name)
        self.storage[self.name] = "directory"

    def write_bytes(self, data):
        self.storage[self.name] = bytes(data)
        return len(data)


class ProbeTests(unittest.TestCase):
    def setUp(self):
        self.guard = ExitStack()
        self.addCleanup(self.guard.close)
        self.guard.enter_context(patch("socket.socket", side_effect=AssertionError("real socket forbidden")))
        self.guard.enter_context(patch("http.client.HTTPConnection", side_effect=AssertionError("real HTTP forbidden")))
        self.guard.enter_context(patch("subprocess.run", side_effect=AssertionError("subprocess forbidden")))

    def analyze(self, data=None, mode="count", expected=None):
        job = deepcopy(probe.fixed_jobs()[0 if mode == "count" else 1])
        return probe.analyze(raw(envelope() if data is None else data), job, EXPECTED if expected is None else expected)

    def assert_rejected(self, report):
        self.assertTrue(report["errors"])
        self.assertFalse(report["coverage_observed_complete"])
        self.assertFalse(report["eligible"])

    def test_fixed_plan_has_exact_three_symbols_and_six_jobs(self):
        jobs = probe.fixed_jobs()
        self.assertEqual(len(jobs), 6)
        self.assertEqual([job["id"] for job in jobs], list(range(1, 7)))
        self.assertEqual([(j["symbol"], j["mode"]) for j in jobs], [
            (symbol, mode) for symbol in ("SH600011", "BJ920000", "SH000300")
            for mode in ("count", "range")])
        self.assertEqual(probe.SYMBOLS, {
            "SH600011": "600011.SH", "BJ920000": "920000.BJ", "SH000300": "000300.SH"})

    def test_fixed_plan_pins_market_date_count_and_adjustment(self):
        for job in probe.fixed_jobs():
            with self.subTest(job=job["id"]):
                payload = job["payload"]
                full = probe.SYMBOLS[job["symbol"]]
                self.assertEqual(payload["market"], 1)
                self.assertEqual(payload["security"], {"market": 1, "code": full[:6], "fullCode": full})
                self.assertEqual(payload["codes"], [full])
                self.assertEqual(payload["limit"], 1200)
                self.assertEqual(payload["period"], 7)
                self.assertIs(type(payload["adjustment"]), int)
                self.assertEqual(payload["adjustment"], 0)
                self.assertEqual(payload["endTimeUtc"], "2026-09-04T15:59:59.999Z")
                self.assertEqual(payload["startTimeUtc"], "2022-08-23T16:00:00Z" if job["mode"] == "range" else None)

    def test_plan_declares_six_reads_and_review_only(self):
        plan = probe.plan()
        self.assertEqual(plan["max_rest_attempts"], 6)
        self.assertEqual(plan["endpoint"], "http://127.0.0.1:17180/api/v2/quotes/candle")
        self.assertEqual(plan["retries"], 0)
        for flag in ("redirects", "proxy", "database_access", "production_writes", "live_trading"):
            self.assertIs(plan[flag], False)

    def test_unknown_or_modified_job_stops_before_network(self):
        for change in ("symbol", "market", "code", "limit", "time"):
            job = deepcopy(probe.fixed_jobs()[0])
            if change == "symbol":
                job["symbol"] = "SH600000"
            elif change == "market":
                job["payload"]["market"] = 2
            elif change == "code":
                job["payload"]["security"]["fullCode"] = "000300.SZ"
            elif change == "limit":
                job["payload"]["limit"] = 5000
            else:
                job["payload"]["endTimeUtc"] = "2026-09-05T15:59:59.999Z"
            with self.subTest(change=change), self.assertRaisesRegex(probe.StopProbe, "request_not_in_fixed_plan"):
                probe.fetch(job, "synthetic-unused-token")

    def test_boolean_payload_cannot_bypass_exact_plan(self):
        for field, value in (("market", True), ("adjustment", False)):
            job = deepcopy(probe.fixed_jobs()[0])
            job["payload"][field] = value
            with self.subTest(field=field), self.assertRaisesRegex(probe.StopProbe, "request_not_in_fixed_plan"):
                probe.fetch(job, "synthetic-unused-token")

    def test_complete_978_unique_rows_exceed_adapter_cap(self):
        report = self.analyze()
        self.assertEqual(report["point_count"], 978)
        self.assertEqual(report["valid_row_count"], 978)
        self.assertEqual(report["unique_date_count"], 978)
        self.assertTrue(report["more_than_500_unique_dates"])
        self.assertTrue(report["coverage_observed_complete"])
        self.assertEqual(report["errors"], [])
        self.assertEqual(report["research"]["missing"], [])
        self.assertEqual(report["warmup"]["missing"], [])

    def test_missing_row_retains_exact_missing_key(self):
        data = envelope()
        del data["data"]["items"][0]["points"][500]
        report = self.analyze(data)
        self.assertFalse(report["coverage_observed_complete"])
        self.assertEqual(report["research"]["missing"], [DAYS[500]])
        self.assertEqual(report["unique_date_count"], 977)

    def test_bad_dates_are_rejected(self):
        for value in ("2026-02-30", "nonsense", True, False, "20261301", "20260904249999"):
            data = envelope()
            data["data"]["items"][0]["points"][0]["values"]["date_time"] = value
            with self.subTest(value=value):
                report = self.analyze(data)
                self.assert_rejected(report)
                self.assertEqual(report["valid_row_count"], 977)

    def test_nan_infinite_boolean_and_invalid_numbers_are_rejected(self):
        for value in ("NaN", float("nan"), "Infinity", float("inf"), True, False, None, {}, "not-a-number"):
            data = envelope()
            data["data"]["items"][0]["points"][0]["values"]["open"] = value
            with self.subTest(value=repr(value)):
                self.assert_rejected(self.analyze(data))

    def test_invalid_ohlc_and_negative_liquidity_are_rejected(self):
        for field, value in (("open", "0"), ("latest", "-1"), ("high", "8"), ("low", "11"),
                             ("transaction_volume", "-1"), ("transaction_amount", "-1")):
            data = envelope()
            data["data"]["items"][0]["points"][0]["values"][field] = value
            with self.subTest(field=field):
                self.assert_rejected(self.analyze(data))

    def test_wrong_or_missing_item_identity_is_rejected(self):
        for identity in ({"fullCode": "000300.SZ"}, {}, {"fullCode": "920000.BJ"}):
            data = envelope()
            data["data"]["items"][0]["security"] = identity
            with self.subTest(identity=identity):
                report = self.analyze(data)
                self.assert_rejected(report)
                self.assertIn("response_security_identity_mismatch_or_missing", report["errors"])

    def test_wrong_point_identity_is_rejected(self):
        data = envelope()
        data["data"]["items"][0]["points"][0]["values"]["full_code"] = "000300.SZ"
        report = self.analyze(data)
        self.assert_rejected(report)
        self.assertEqual(report["valid_row_count"], 977)

    def test_disagreeing_dual_dates_are_rejected(self):
        data = envelope()
        data["data"]["items"][0]["points"][0]["timestampUtc"] = DAYS[1] + "T00:00:00Z"
        self.assert_rejected(self.analyze(data))

    def test_date_normalization_uses_china_calendar_day(self):
        for value, expected in (("2022-08-23T16:00:00Z", "2022-08-24"),
                                ("20220824", "2022-08-24"), (20220824150000, "2022-08-24")):
            with self.subTest(value=value):
                self.assertEqual(probe.date_value(value), expected)

    def test_timestamp_fallback_without_value_date_is_allowed(self):
        data = envelope()
        del data["data"]["items"][0]["points"][0]["values"]["date_time"]
        self.assertTrue(self.analyze(data)["coverage_observed_complete"])

    def test_timestamp_requires_explicit_timezone(self):
        for timestamp in (DAYS[0], DAYS[0] + "T00:00:00", "20220824"):
            data = envelope()
            data["data"]["items"][0]["points"][0]["timestampUtc"] = timestamp
            with self.subTest(timestamp=timestamp):
                self.assert_rejected(self.analyze(data))

    def test_duplicate_date_is_not_hidden_by_set_coverage(self):
        data = envelope()
        data["data"]["items"][0]["points"].append(deepcopy(data["data"]["items"][0]["points"][0]))
        report = self.analyze(data)
        self.assert_rejected(report)
        self.assertEqual(report["unique_date_count"], 978)
        self.assertEqual(report["duplicate_date_count"], 1)
        self.assertIn("duplicate_dates", report["errors"])

    def test_count_allows_history_before_contract_start(self):
        report = self.analyze(envelope(["2022-08-23"] + DAYS))
        self.assertTrue(report["coverage_observed_complete"])
        self.assertEqual(report["dates_before_start"], ["2022-08-23"])
        self.assertEqual(report["errors"], [])

    def test_range_rejects_history_before_requested_start(self):
        report = self.analyze(envelope(["2022-08-23"] + DAYS), mode="range")
        self.assert_rejected(report)
        self.assertIn("outside_requested_date_window", report["errors"])

    def test_both_modes_reject_dates_after_end(self):
        for mode in ("count", "range"):
            with self.subTest(mode=mode):
                report = self.analyze(envelope(DAYS + ["2026-09-07"]), mode=mode)
                self.assert_rejected(report)
                self.assertIn("outside_requested_date_window", report["errors"])

    def test_unexpected_date_inside_contract_is_rejected(self):
        report = self.analyze(envelope(DAYS + ["2022-08-27"]))
        self.assert_rejected(report)
        self.assertEqual(report["unexpected_in_target_dates"], ["2022-08-27"])

    def test_response_shape_and_adjustment_fail_closed(self):
        invalid = [[], {"ok": False}, {"ok": 1, "data": {}}, {"ok": True, "data": []},
                   {"ok": True, "data": {"items": []}}]
        data = envelope()
        data["data"]["adjustment"] = 1
        invalid.append(data)
        for index, data in enumerate(invalid):
            with self.subTest(index=index):
                self.assert_rejected(self.analyze(data))

    def test_boolean_adjustment_echo_is_rejected(self):
        for adjustment in (True, False):
            data = envelope()
            data["data"]["adjustment"] = adjustment
            with self.subTest(adjustment=adjustment):
                report = self.analyze(data)
                self.assert_rejected(report)
                self.assertIn("adjustment_echo_mismatch", report["errors"])

    def test_complete_observation_never_proves_basis_or_eligibility(self):
        report = self.analyze()
        self.assertTrue(report["coverage_observed_complete"])
        self.assertIs(report["eligible"], False)
        for field in ("vendor_basis", "historical_identity", "volume_unit", "amount_unit"):
            self.assertEqual(report[field], "unverified")

    def test_stock_requires_volume_amount_while_benchmark_can_omit(self):
        data = envelope()
        for field in ("transaction_volume", "transaction_amount"):
            del data["data"]["items"][0]["points"][0]["values"][field]
        self.assert_rejected(self.analyze(data))
        expected = deepcopy(EXPECTED)
        expected["benchmark"] = True
        report = self.analyze(data, expected=expected)
        self.assertTrue(report["coverage_observed_complete"])
        self.assertIs(report["eligible"], False)

    def test_pair_uses_numeric_equivalence_and_keeps_basis_unproved(self):
        data = envelope()
        values = data["data"]["items"][0]["points"][0]["values"]
        values.update({"open": 10, "high": "12.0000", "low": "9.000", "latest": 11.0,
                       "transaction_volume": "1E3", "transaction_amount": 11000})
        pair = probe.compare_pair(self.analyze(), self.analyze(data, mode="range"))
        self.assertTrue(pair["comparable"])
        self.assertTrue(pair["both_complete"])
        self.assertEqual(pair["overlap_dates"], 978)
        self.assertEqual(pair["mismatch_dates"], [])
        self.assertIs(pair["price_basis_proved"], False)

    def test_pair_reports_real_numeric_difference(self):
        data = envelope()
        data["data"]["items"][0]["points"][400]["values"]["latest"] = "11.01"
        pair = probe.compare_pair(self.analyze(), self.analyze(data, mode="range"))
        self.assertEqual(pair["mismatch_dates"], [DAYS[400]])

    def test_pair_duplicate_keys_make_comparison_unusable(self):
        data = envelope()
        data["data"]["items"][0]["points"].append(deepcopy(data["data"]["items"][0]["points"][0]))
        pair = probe.compare_pair(self.analyze(), self.analyze(data, mode="range"))
        self.assertEqual(pair, {"comparable": False, "reason": "duplicate_dates"})

    def test_pair_reports_range_dates_absent_from_count(self):
        pair = probe.compare_pair(self.analyze(envelope(DAYS[1:])), self.analyze(mode="range"))
        self.assertEqual(pair["range_dates_missing_from_count"], [DAYS[0]])
        self.assertFalse(pair["both_complete"])

    def transport_mocks(self, body=b"synthetic raw response", *, status=200, clock=None):
        """Supply every transport object in memory; no real timer or socket exists."""
        stream = io.BytesIO(body)
        response = Mock(name="synthetic HTTP response")
        response.status = status
        response.read1.side_effect = stream.read1
        connection = Mock(name="synthetic HTTP connection")
        connection.sock = Mock(name="synthetic socket")
        connection.getresponse.return_value = response
        timer = Mock(name="synthetic watchdog; never starts a thread")
        stack = ExitStack()
        self.addCleanup(stack.close)
        factory = stack.enter_context(patch.object(probe.http.client, "HTTPConnection", return_value=connection))
        timer_factory = stack.enter_context(patch.object(probe.threading, "Timer", return_value=timer))
        stack.enter_context(patch.object(probe.time, "monotonic", return_value=0.0, side_effect=clock))
        return connection, response, factory, timer, timer_factory

    def test_fetch_fixed_post_and_synthetic_auth_header_stay_in_memory(self):
        connection, _, factory, timer, timer_factory = self.transport_mocks()
        job = probe.fixed_jobs()[0]
        token = "aBcD" * 16  # Synthetic marker, never read from a credential store.
        with redirect_stdout(io.StringIO()) as output:
            probe.fetch(job, token)
        self.assertEqual(output.getvalue(), "")
        factory.assert_called_once_with("127.0.0.1", 17180, timeout=probe.TIMEOUT)
        connection.connect.assert_called_once_with()
        connection.request.assert_called_once()
        method, route, body, headers = connection.request.call_args.args
        self.assertEqual((method, route), ("POST", "/api/v2/quotes/candle"))
        self.assertEqual(json.loads(body), job["payload"])
        self.assertEqual(headers["X-Tonghuasun-Codex-Token"], token)
        self.assertEqual(headers["Accept-Encoding"], "identity")
        self.assertEqual(headers["Content-Type"], "application/json")
        self.assertEqual(timer_factory.call_args.args[0], probe.TIMEOUT)
        timer.start.assert_called_once_with()
        timer.cancel.assert_called_once_with()
        connection.close.assert_called_once_with()

    def test_fetch_returns_200_original_bytes_without_decoding(self):
        original = b"\x00\xff\x80synthetic\r\nraw\x00response"
        connection, response, _, timer, _ = self.transport_mocks(original)
        status, received = probe.fetch(probe.fixed_jobs()[0], "a" * 64)
        self.assertEqual(status, 200)
        self.assertEqual(received, original)
        self.assertGreaterEqual(response.read1.call_count, 2)
        timer.cancel.assert_called_once_with()
        connection.close.assert_called_once_with()

    def test_fetch_non_200_and_redirect_never_follow_or_retry(self):
        for status in (302, 307, 403, 503):
            with self.subTest(status=status):
                original = b"synthetic status response"
                connection, response, factory, timer, _ = self.transport_mocks(original, status=status)
                response.getheader.return_value = "https://invalid.example/never-follow"
                self.assertEqual(probe.fetch(probe.fixed_jobs()[0], "a" * 64), (status, original))
                factory.assert_called_once()
                connection.request.assert_called_once()
                response.getheader.assert_not_called()
                timer.cancel.assert_called_once_with()
                connection.close.assert_called_once_with()

    def test_fetch_response_size_exact_limit_passes_one_extra_byte_rejected(self):
        for length in (16, 17):
            with self.subTest(length=length), patch.object(probe, "MAX_BYTES", 16):
                connection, _, factory, timer, _ = self.transport_mocks(b"x" * length)
                if length == 16:
                    self.assertEqual(probe.fetch(probe.fixed_jobs()[0], "a" * 64), (200, b"x" * 16))
                else:
                    with self.assertRaisesRegex(probe.StopProbe, "^response_size_limit_exceeded$"):
                        probe.fetch(probe.fixed_jobs()[0], "a" * 64)
                factory.assert_called_once()
                timer.cancel.assert_called_once_with()
                connection.close.assert_called_once_with()

    def test_fetch_token_echo_is_rejected_case_insensitively(self):
        token = "aBcD" * 16
        connection, _, factory, timer, _ = self.transport_mocks(b"prefix:" + token.upper().encode("ascii") + b":suffix")
        with self.assertRaisesRegex(probe.StopProbe, "^credential_echo_raw_not_retained$") as caught:
            probe.fetch(probe.fixed_jobs()[0], token)
        self.assertNotIn(token.lower(), str(caught.exception).lower())
        factory.assert_called_once()
        timer.cancel.assert_called_once_with()
        connection.close.assert_called_once_with()

    def test_fetch_deadline_checks_stop_connect_request_or_read_progress(self):
        cases = (([0.0, probe.TIMEOUT + 1], 0, 0),
                 ([0.0, 0.0, probe.TIMEOUT + 1], 1, 0),
                 ([0.0, 0.0, 0.0, probe.TIMEOUT + 1], 1, 1))
        for clock, expected_requests, expected_response_reads in cases:
            with self.subTest(clock=clock):
                connection, response, _, timer, _ = self.transport_mocks(clock=clock)
                with self.assertRaisesRegex(probe.StopProbe, "^request_deadline_exceeded$"):
                    probe.fetch(probe.fixed_jobs()[0], "a" * 64)
                self.assertEqual(connection.request.call_count, expected_requests)
                self.assertEqual(connection.getresponse.call_count, expected_response_reads)
                response.read1.assert_not_called()
                timer.cancel.assert_called_once_with()
                connection.close.assert_called_once_with()

    def test_fetch_watchdog_closes_socket_and_rejects_partial_response(self):
        connection, response, _, timer, timer_factory = self.transport_mocks()
        reads = 0

        def timeout_during_read(amount):
            nonlocal reads
            reads += 1
            if reads == 1:
                timer_factory.call_args.args[1]()  # Invoke watchdog synchronously; never start a thread.
                return b"synthetic partial response"
            return b""

        response.read1.side_effect = timeout_during_read
        with self.assertRaisesRegex(probe.StopProbe, "^request_deadline_exceeded$"):
            probe.fetch(probe.fixed_jobs()[0], "a" * 64)
        connection.sock.shutdown.assert_called_once_with(probe.socket.SHUT_RDWR)
        timer.cancel.assert_called_once_with()
        connection.close.assert_called_once_with()

    def capture_mocks(self, *, existing=False, fetch_effect=None):
        storage = {}
        virtual = MemoryPath("in-memory-audit-capture", storage)
        if existing:
            storage[str(virtual)] = "existing authorization claim"

        def write(path, data, *, exclusive=False):
            name = str(path)
            if exclusive and name in storage:
                raise FileExistsError(name)
            storage[name] = deepcopy(data)

        def fetch(job, token):
            # Every HTTP response here is synthesized in memory; no socket is opened.
            return 200, raw(envelope(full_code=job["payload"]["security"]["fullCode"]))

        stack = ExitStack()
        self.addCleanup(stack.close)
        stack.enter_context(patch.object(probe, "LIVE", virtual))
        stack.enter_context(patch.object(probe, "write_json", side_effect=write))
        stack.enter_context(patch.object(probe, "expected_keys", return_value={s: deepcopy(EXPECTED) for s in probe.SYMBOLS}))
        stack.enter_context(patch.object(probe, "get_preflight", return_value={"passed": True, "synthetic": True}))
        stack.enter_context(patch.object(probe, "local_credentials", return_value="a" * 64))
        fetch_mock = stack.enter_context(patch.object(probe, "fetch", side_effect=fetch if fetch_effect is None else fetch_effect))
        # Source-pin reads are also synthetic, so capture cannot read any local credentials or datasets.
        stack.enter_context(patch.object(Path, "read_bytes", return_value=b"synthetic offline pin input"))
        stack.enter_context(patch.object(probe.time, "monotonic", return_value=0.0))
        stack.enter_context(patch.object(probe.time, "sleep"))
        stack.enter_context(redirect_stdout(io.StringIO()))
        return storage, virtual, fetch_mock

    def test_capture_six_attempt_ceiling_with_all_io_mocked(self):
        storage, virtual, fetch = self.capture_mocks()
        self.assertEqual(probe.capture(), 0)
        self.assertEqual(fetch.call_count, 6)
        summary = storage[str(virtual / "summary.json")]
        self.assertEqual(summary["rest_attempts_consumed"], 6)
        self.assertEqual(summary["rest_attempts_not_issued"], 0)
        self.assertIs(summary["automatic_resume_allowed"], False)
        self.assertIs(summary["m2_accepted"], False)
        self.assertIs(summary["eligible"], False)
        self.assertEqual(len(summary["pairs"]), 3)

    def test_capture_reserves_attempt_before_fetch_and_never_retries(self):
        holder = {}

        def failed_fetch(job, token):
            storage, virtual = holder["storage"], holder["virtual"]
            self.assertEqual(storage[str(virtual / "attempt_1.json")]["state"], "reserved_before_network")
            raise OSError("synthetic transport failure")

        storage, virtual, fetch = self.capture_mocks(fetch_effect=failed_fetch)
        holder.update(storage=storage, virtual=virtual)
        self.assertEqual(probe.capture(), 1)
        self.assertEqual(fetch.call_count, 1)
        summary = storage[str(virtual / "summary.json")]
        self.assertEqual(summary["rest_attempts_consumed"], 1)
        self.assertEqual(summary["rest_attempts_not_issued"], 5)
        self.assertEqual(summary["stop_reason"], "transport_failed_or_timed_out_no_retry")

    def test_capture_existing_claim_prevents_requests(self):
        _, _, fetch = self.capture_mocks(existing=True)
        with self.assertRaises(FileExistsError):
            probe.capture()
        fetch.assert_not_called()

    def test_capture_http_failure_stops_without_retry(self):
        storage, virtual, fetch = self.capture_mocks(fetch_effect=lambda job, token: (503, b"synthetic unavailable"))
        self.assertEqual(probe.capture(), 1)
        self.assertEqual(fetch.call_count, 1)
        self.assertEqual(storage[str(virtual / "summary.json")]["stop_reason"], "http_status_503_stop_no_retry")

    def test_capture_item_identity_failure_stops_without_retry(self):
        storage, virtual, fetch = self.capture_mocks(fetch_effect=lambda job, token: (200, raw(envelope(full_code="000300.SZ"))))
        self.assertEqual(probe.capture(), 1)
        self.assertEqual(fetch.call_count, 1)
        self.assertEqual(storage[str(virtual / "summary.json")]["stop_reason"], "response_contract_failure")

    def test_capture_point_identity_failure_stops_without_retry(self):
        data = envelope()
        data["data"]["items"][0]["points"][0]["values"]["full_code"] = "000300.SZ"
        storage, virtual, fetch = self.capture_mocks(fetch_effect=lambda job, token: (200, raw(data)))
        self.assertEqual(probe.capture(), 1)
        self.assertEqual(fetch.call_count, 1)
        self.assertEqual(storage[str(virtual / "summary.json")]["stop_reason"], "response_contract_failure")


if __name__ == "__main__":
    unittest.main(verbosity=2)
