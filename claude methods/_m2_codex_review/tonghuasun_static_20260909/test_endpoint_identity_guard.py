"""Synthetic tests; never load an endpoint/configuration or use a real network."""
from __future__ import annotations

from contextlib import ExitStack
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch


HERE = Path(__file__).resolve().parent
with ExitStack() as import_guard:
    import_guard.enter_context(patch("socket.socket", side_effect=AssertionError("real socket forbidden")))
    import_guard.enter_context(patch("http.client.HTTPConnection", side_effect=AssertionError("real HTTP forbidden")))
    import_guard.enter_context(patch("subprocess.run", side_effect=AssertionError("subprocess forbidden")))
    spec = importlib.util.spec_from_file_location("endpoint_identity_guard_under_test", HERE / "endpoint_identity_guard.py")
    guard = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(guard)


HOST_TIME = datetime(2026, 9, 9, 16, 8, 53, tzinfo=timezone.utc)
CURRENT_PID = 29876
ENDPOINT = {
    "baseUrl": "http://127.0.0.1:17180", "port": 17180,
    "processId": CURRENT_PID,
    "startedAtUtc": "2026-09-09T16:09:03Z",
    "listenAddresses": ["127.0.0.1"], "lanBaseUrls": [],
}


class EndpointIdentityGuardTests(unittest.TestCase):
    def setUp(self):
        self.protection = ExitStack()
        self.addCleanup(self.protection.close)
        for name in ("socket.socket", "http.client.HTTPConnection", "subprocess.run", "builtins.open"):
            self.protection.enter_context(patch(name, side_effect=AssertionError("external effect forbidden")))
        self.protection.enter_context(patch.object(Path, "open", side_effect=AssertionError("file read forbidden")))

    def check(self, endpoint=None, *, current_pid=CURRENT_PID, host_created_at=HOST_TIME, endpoint_mtime=None):
        return guard.validate_endpoint_identity(
            deepcopy(ENDPOINT) if endpoint is None else endpoint,
            current_pid=current_pid,
            host_created_at=host_created_at,
            endpoint_mtime=HOST_TIME + timedelta(seconds=11) if endpoint_mtime is None else endpoint_mtime,
        )

    def assert_denied(self, result, error):
        self.assertIs(result["passed"], False)
        self.assertIn(error, result["errors"])

    def test_current_pid_and_fresh_explicit_loopback_metadata_pass(self):
        self.assertEqual(self.check(), {"passed": True, "errors": []})

    def test_non_object_metadata_fails_closed(self):
        for value in (None, [], "metadata", True, 17180):
            with self.subTest(value=value):
                self.assert_denied(guard.validate_endpoint_identity(value, current_pid=CURRENT_PID,
                    host_created_at=HOST_TIME, endpoint_mtime=HOST_TIME), "endpoint_metadata_not_object")

    def test_stale_process_id_is_rejected(self):
        endpoint = deepcopy(ENDPOINT)
        endpoint["processId"] = 23512
        self.assert_denied(self.check(endpoint), "endpoint_process_id_mismatch")

    def test_pid_reuse_with_old_start_time_is_rejected(self):
        endpoint = deepcopy(ENDPOINT)
        endpoint["startedAtUtc"] = "2026-09-04T10:03:42.622042Z"
        self.assert_denied(self.check(endpoint), "endpoint_start_outside_host_start_window")

    def test_bool_float_string_and_nonpositive_endpoint_pids_are_rejected(self):
        for value in (True, False, float(CURRENT_PID), str(CURRENT_PID), 0, -1, None):
            endpoint = deepcopy(ENDPOINT)
            endpoint["processId"] = value
            with self.subTest(value=value):
                self.assert_denied(self.check(endpoint), "endpoint_process_id_invalid")

    def test_current_pid_must_also_be_a_positive_nonboolean_integer(self):
        for value in (True, False, float(CURRENT_PID), str(CURRENT_PID), 0, -1, None):
            with self.subTest(value=value):
                self.assert_denied(self.check(current_pid=value), "current_process_id_invalid")

    def test_origin_must_match_exact_loopback_http_and_port(self):
        for url in ("http://localhost:17180", "http://127.0.0.1:17181", "https://127.0.0.1:17180",
                    "http://127.0.0.1:17180/", "http://127.0.0.1:17180/api", "http://192.168.1.2:17180",
                    "http://127.0.0.1:17180@invalid.example", "http://[::1]:17180", None):
            endpoint = deepcopy(ENDPOINT)
            endpoint["baseUrl"] = url
            with self.subTest(url=url):
                self.assert_denied(self.check(endpoint), "endpoint_origin_not_exact_loopback")

    def test_port_must_be_exact_nonboolean_integer(self):
        for value in (True, False, 17180.0, "17180", 17181, None):
            endpoint = deepcopy(ENDPOINT)
            endpoint["port"] = value
            with self.subTest(value=value):
                self.assert_denied(self.check(endpoint), "endpoint_port_invalid")

    def test_listen_addresses_require_exact_single_loopback(self):
        for addresses in ([], ["0.0.0.0"], ["::1"], ["127.0.0.1", "192.168.1.2"],
                          ["127.0.0.1", "127.0.0.1"], "127.0.0.1", ("127.0.0.1",), None):
            endpoint = deepcopy(ENDPOINT)
            endpoint["listenAddresses"] = addresses
            with self.subTest(addresses=addresses):
                self.assert_denied(self.check(endpoint), "listen_addresses_not_exact_loopback")

    def test_lan_base_urls_must_be_an_explicit_empty_list(self):
        for urls in (["http://192.168.1.2:17180"], ["http://127.0.0.1:17180"], "", (), {}, False, None):
            endpoint = deepcopy(ENDPOINT)
            endpoint["lanBaseUrls"] = urls
            with self.subTest(urls=urls):
                self.assert_denied(self.check(endpoint), "lan_base_urls_not_explicitly_empty")

    def test_every_required_endpoint_field_missing_fails_closed(self):
        for key in ENDPOINT:
            endpoint = deepcopy(ENDPOINT)
            del endpoint[key]
            with self.subTest(key=key):
                self.assertIs(self.check(endpoint)["passed"], False)

    def test_start_requires_valid_explicit_timezone(self):
        for value in (None, "", "2026-09-09T16:09:03", "2026-09-09", "2026-02-30T00:00:00Z",
                      "nonsense", True, 1788960543, HOST_TIME.replace(tzinfo=None)):
            endpoint = deepcopy(ENDPOINT)
            endpoint["startedAtUtc"] = value
            with self.subTest(value=str(value)):
                self.assert_denied(self.check(endpoint), "endpoint_start_time_invalid_or_timezone_missing")

    def test_host_creation_and_mtime_require_timezone(self):
        for field, error in (("host_created_at", "host_creation_time_invalid_or_timezone_missing"),
                             ("endpoint_mtime", "endpoint_mtime_invalid_or_timezone_missing")):
            for value in ("", "bad", "2026-09-09T16:08:53", True, HOST_TIME.replace(tzinfo=None)):
                with self.subTest(field=field, value=str(value)):
                    self.assert_denied(self.check(**{field: value}), error)

    def test_missing_host_and_mtime_fail_closed(self):
        result = guard.validate_endpoint_identity(ENDPOINT, current_pid=CURRENT_PID,
            host_created_at=None, endpoint_mtime=None)
        self.assert_denied(result, "host_creation_time_invalid_or_timezone_missing")
        self.assertIn("endpoint_mtime_invalid_or_timezone_missing", result["errors"])

    def test_start_window_is_inclusive_at_minus_two_and_plus_300_seconds(self):
        for delta in (-2, 0, 300):
            endpoint = deepcopy(ENDPOINT)
            endpoint["startedAtUtc"] = HOST_TIME + timedelta(seconds=delta)
            with self.subTest(delta=delta):
                self.assertIs(self.check(endpoint)["passed"], True)

    def test_start_outside_either_boundary_is_rejected(self):
        for delta in (-2.000001, 300.000001):
            endpoint = deepcopy(ENDPOINT)
            endpoint["startedAtUtc"] = HOST_TIME + timedelta(seconds=delta)
            with self.subTest(delta=delta):
                self.assert_denied(self.check(endpoint), "endpoint_start_outside_host_start_window")

    def test_mtime_older_than_host_minus_two_seconds_is_rejected(self):
        for delta in (-2.000001, -86400):
            with self.subTest(delta=delta):
                self.assert_denied(self.check(endpoint_mtime=HOST_TIME + timedelta(seconds=delta)),
                    "endpoint_mtime_predates_host_start_window")

    def test_mtime_at_lower_boundary_or_after_host_passes(self):
        for delta in (-2, 0, 11, 86400):
            with self.subTest(delta=delta):
                self.assertIs(self.check(endpoint_mtime=HOST_TIME + timedelta(seconds=delta))["passed"], True)

    def test_equivalent_non_utc_offsets_are_compared_by_instant(self):
        endpoint = deepcopy(ENDPOINT)
        endpoint["startedAtUtc"] = "2026-09-10T00:09:03+08:00"
        self.assertEqual(self.check(endpoint, host_created_at="2026-09-10T00:08:53+08:00",
            endpoint_mtime="2026-09-09T09:09:04-07:00"), {"passed": True, "errors": []})

    def test_multiple_failures_accumulate_without_echoing_input_or_mutating_it(self):
        endpoint = deepcopy(ENDPOINT)
        endpoint.update({"processId": 23512, "startedAtUtc": "2026-09-04T10:03:42Z",
                         "opaqueExtra": "synthetic-private-marker", "baseUrl": "synthetic-private-marker"})
        before = deepcopy(endpoint)
        result = self.check(endpoint, endpoint_mtime="2026-09-04T10:03:43Z")
        self.assertEqual(endpoint, before)
        self.assertEqual(len(result["errors"]), 4)
        self.assertNotIn("synthetic-private-marker", str(result))
        self.assertEqual(set(result), {"passed", "errors"})


if __name__ == "__main__":
    unittest.main(verbosity=2)
