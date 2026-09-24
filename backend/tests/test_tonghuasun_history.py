"""Run directly with unittest; no pytest conftest or production initialization."""
from __future__ import annotations

import ast
from copy import deepcopy
from datetime import date, datetime, timedelta, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import sys
import unittest


BACKEND = Path(__file__).resolve().parents[1]
MODULE_PATH = BACKEND / "app/data/tonghuasun_history.py"
module_spec = importlib.util.spec_from_file_location("isolated_ths_history", MODULE_PATH)
history = importlib.util.module_from_spec(module_spec)
sys.modules[module_spec.name] = history
module_spec.loader.exec_module(history)
SecuritySpec = history.SecuritySpec
Error = history.HistoryValidationError


def envelope(spec, dates=("2022-08-24", "2022-08-25")):
    points = []
    for day in dates:
        timestamp = datetime.combine(date.fromisoformat(day), datetime.min.time(),
                                     timezone(timedelta(hours=8))).astimezone(timezone.utc)
        points.append({"timestampUtc": timestamp.isoformat().replace("+00:00", "Z"),
                       "values": {"full_code": spec.response_full_code,
                                  "security_name": "测试证券", "date_time": int(day.replace("-", "")),
                                  "open": 10, "high": 12, "low": 9, "latest": 11,
                                  "transaction_volume": 123400,
                                  "transaction_amount": 1357400}})
    return {"ok": True, "data": {"items": [{"security": {
        "market": 1, "fullCode": spec.response_full_code,
        "code": spec.response_code, "hostMarketCode": spec.host_market_code,
        "hostFullCode": spec.host_full_code, "name": ""}, "points": points}]}}


def encode(value):
    return json.dumps(value, ensure_ascii=False).encode("utf-8")


class HistoryTests(unittest.TestCase):
    def test_risk_board_requires_explicit_same_exchange_identity_evidence(self):
        spec=SecuritySpec.stock('SH600289',host_full_code='USHT600289',mapping_evidence='synthetic retained security-search receipt')
        result=history.parse_history_response(encode(envelope(spec)),spec,'2022-08-24','2022-08-25')
        self.assertEqual(result['response_identity']['hostFullCode'],'USHT600289')
        self.assertFalse(result['mapping_verified'])
        self.assert_error('stock_market_mapping_evidence_required',lambda: SecuritySpec.stock('SH600289',host_full_code='USHT600289'))
        for wrong in ('USZT600289','USHI600289','USHT600290','USHB600289'):
            self.assert_error('invalid_stock_identity_spec',lambda: SecuritySpec.stock('SH600289',host_full_code=wrong,mapping_evidence='fixture'))

    def setUp(self):
        self.stock = SecuritySpec.stock("SH600011")
        self.index = SecuritySpec.benchmark(
            "SH000300", host_full_code="USZI399300", response_full_code="399300.SZ",
            mapping_evidence="synthetic-test-mapping-not-a-real-acceptance")

    def parse(self, body=None, spec=None, **kwargs):
        spec = spec or self.stock
        if body is None:
            body = envelope(spec)
        return history.parse_history_response(encode(body), spec, "2022-08-24", "2022-08-25",
                                              **kwargs)

    def assert_error(self, code, function):
        with self.assertRaises(Error) as caught:
            function()
        self.assertEqual(caught.exception.code, code)
        self.assertEqual(str(caught.exception), code)

    def test_stock_request_uses_only_one_full_identifier_and_china_dates(self):
        request = history.build_history_request(self.stock, "2022-08-24", "2026-09-04")
        self.assertEqual(request["security"], {"market": 1, "fullCode": "600011.SH"})
        self.assertNotIn("codes", request)
        self.assertEqual(request["startTimeUtc"], "2022-08-23T16:00:00.000Z")
        self.assertEqual(request["endTimeUtc"], "2026-09-04T15:59:59.999Z")
        self.assertEqual((request["period"], request["adjustment"], request["limit"]), (7, 0, 5000))

    def test_index_native_request_keeps_canonical_identity_separate(self):
        request = history.build_history_request(self.index, "2022-08-24", "2022-08-25")
        self.assertEqual(request["security"], {"market": 1, "hostFullCode": "USZI399300"})
        self.assertNotIn("codes", request)
        result = self.parse(spec=self.index)
        self.assertEqual(result["canonical_symbol"], "SH000300")
        self.assertEqual(result["response_identity"]["fullCode"], "399300.SZ")
        self.assertFalse(result["mapping_verified"])
        self.assertFalse(result["eligible"])

    def test_alphanumeric_index_host_code_is_preserved(self):
        index = SecuritySpec.benchmark("SH000001", host_full_code="USHI1A0001",
            response_full_code="1A0001.SH", mapping_evidence="synthetic-static-candidate")
        self.assertEqual(self.parse(spec=index)["response_identity"]["code"], "1A0001")

    def test_observed_formatter_alias_does_not_change_host_or_canonical_code(self):
        index = SecuritySpec.benchmark("SH000001", host_full_code="USHI1A0001",
            response_full_code="10001.SH", mapping_evidence="synthetic-formatter-alias-evidence")
        result = self.parse(spec=index)
        self.assertEqual(result["canonical_symbol"], "SH000001")
        self.assertEqual(result["response_identity"]["fullCode"], "10001.SH")
        self.assertEqual(result["response_identity"]["hostFullCode"], "USHI1A0001")
        unobserved_spec = SecuritySpec.benchmark("SH000001", host_full_code="USHI1A0001",
            response_full_code="1A0001.SH", mapping_evidence="synthetic-static-candidate")
        self.assert_error("response_identity_mismatch",
            lambda: self.parse(envelope(index), unobserved_spec))
        body = envelope(index)
        body["data"]["items"][0]["security"]["hostFullCode"] = "USHI10001"
        self.assert_error("response_identity_mismatch", lambda: self.parse(body, index))

    def test_alias_requires_evidence_and_consistent_native_exchange(self):
        self.assert_error("benchmark_mapping_evidence_required", lambda: SecuritySpec.benchmark(
            "SH000300", host_full_code="USZI399300", response_full_code="399300.SZ", mapping_evidence=""))
        self.assert_error("inconsistent_benchmark_host_identity", lambda: SecuritySpec.benchmark(
            "SH000300", host_full_code="USZI399300", response_full_code="399300.SH", mapping_evidence="fixture"))
        self.assert_error("invalid_benchmark_host_identity", lambda: SecuritySpec.benchmark(
            "SH000300", host_full_code="USHA000300", response_full_code="000300.SH", mapping_evidence="fixture"))

    def test_request_rejects_bad_dates_ranges_modes_and_limits(self):
        for start, end in (("2022-02-30", "2022-03-01"), ("2022-8-24", "2022-08-25"),
                           ("2022-08-25", "2022-08-24")):
            with self.subTest(start=start):
                with self.assertRaises(Error):
                    history.build_history_request(self.stock, start, end)
        for limit in (0, -1, True, 5001, 500.5):
            self.assert_error("invalid_request_limit", lambda: history.build_history_request(
                self.stock, "2022-08-24", "2022-08-25", limit=limit))
        self.assert_error("invalid_requested_adjustment", lambda: history.build_history_request(
            self.stock, "2022-08-24", "2022-08-25", adjustment="raw"))

    def test_history_is_not_tail_clipped_or_volume_rescaled(self):
        dates = [(date(2022, 1, 1) + timedelta(days=i)).isoformat() for i in range(1201)]
        raw = encode(envelope(self.stock, dates))
        result = history.parse_history_response(raw, self.stock, dates[0], dates[-1], expected_dates=dates)
        self.assertEqual(len(result["rows"]), 1201)
        self.assertEqual(result["rows"][0]["volume"], 123400)
        self.assertEqual([row["point_index"] for row in result["rows"]], list(range(1201)))
        self.assertEqual(result["raw_sha256"], hashlib.sha256(raw).hexdigest())
        self.assertTrue(result["coverage"]["complete"])
        self.assertEqual(result["first_date"], dates[0])

    def test_basis_units_and_eligibility_do_not_follow_request_or_echo(self):
        for echo in (None, 0):
            body = envelope(self.stock)
            if echo is not None:
                body["data"]["adjustment"] = echo
            result = self.parse(body, expected_dates=["2022-08-24", "2022-08-25"])
            self.assertEqual(result["requested_adjustment"], "none")
            for field in ("vendor_basis", "volume_unit", "amount_unit"):
                self.assertEqual(result[field], "unverified")
            self.assertFalse(result["eligible"])
        for echo in (1, True, "0"):
            body = envelope(self.stock)
            body["data"]["adjustment"] = echo
            self.assert_error("response_adjustment_mismatch", lambda: self.parse(body))

    def test_missing_extra_and_unsupplied_expected_keys_never_pass_coverage(self):
        body = envelope(self.stock, ["2022-08-24"])
        result = self.parse(body, expected_dates=["2022-08-24", "2022-08-25"])
        self.assertEqual(result["coverage"]["missing_dates"], ["2022-08-25"])
        self.assertFalse(result["coverage"]["complete"])
        result = self.parse(expected_dates=["2022-08-24"])
        self.assertEqual(result["coverage"]["extra_dates"], ["2022-08-25"])
        self.assertFalse(result["coverage"]["complete"])
        self.assertFalse(self.parse()["coverage"]["complete"])

    def test_invalid_expected_domain_is_rejected(self):
        for expected, code in ((["2022-08-24", "2022-08-24"], "duplicate_expected_date"),
                               (["2022-08-23"], "expected_date_outside_window"),
                               ("2022-08-24", "invalid_expected_dates")):
            self.assert_error(code, lambda: self.parse(expected_dates=expected))

    def test_rejects_two_empty_index_items_instead_of_merging(self):
        body = envelope(self.index)
        first = body["data"]["items"][0]
        first["points"] = []
        body["data"]["items"].append(deepcopy(first))
        self.assert_error("response_requires_single_item", lambda: self.parse(body, self.index))
        body["data"]["items"].pop()
        self.assert_error("empty_or_invalid_points", lambda: self.parse(body, self.index))

    def test_rejects_item_host_mismatch_even_if_generic_code_matches(self):
        for field, wrong in (("hostMarketCode", "USHA"), ("hostFullCode", "USHA399300"),
                             ("fullCode", "000300.SH"), ("code", "000300"), ("market", True)):
            body = envelope(self.index)
            body["data"]["items"][0]["security"][field] = wrong
            self.assert_error("response_identity_mismatch", lambda: self.parse(body, self.index))

    def test_rejects_wrong_point_and_conflicting_native_identity(self):
        for field, wrong in (("full_code", "600011.SZ"), ("hostFullCode", "USZA600011"),
                             ("code", "000001")):
            body = envelope(self.stock)
            body["data"]["items"][0]["points"][0]["values"][field] = wrong
            self.assert_error("point_identity_mismatch", lambda: self.parse(body))

    def test_duplicate_unordered_outside_and_inconsistent_dates_rejected(self):
        for dates, code in ((["2022-08-24", "2022-08-24"], "duplicate_trade_date"),
                            (["2022-08-25", "2022-08-24"], "unordered_trade_dates"),
                            (["2022-08-23"], "point_outside_contract_window")):
            self.assert_error(code, lambda: self.parse(envelope(self.stock, dates)))
        body = envelope(self.stock)
        body["data"]["items"][0]["points"][0]["timestampUtc"] = "2022-08-24T16:00:00Z"
        self.assert_error("timestamp_trade_date_mismatch", lambda: self.parse(body))
        body["data"]["items"][0]["points"][0]["timestampUtc"] = "2022-08-24T00:00:00"
        self.assert_error("point_timestamp_timezone_required", lambda: self.parse(body))

    def test_ohlc_amount_and_nonfinite_values_fail_closed(self):
        mutations = (("open", 0, "nonpositive_ohlc"), ("high", 8, "invalid_ohlc_order"),
                     ("low", 11, "invalid_ohlc_order"), ("transaction_volume", -1, "negative_volume_or_amount"),
                     ("transaction_amount", None, "invalid_amount"), ("latest", True, "invalid_close"),
                     ("latest", "NaN", "invalid_close"))
        for field, value, code in mutations:
            body = envelope(self.stock)
            body["data"]["items"][0]["points"][0]["values"][field] = value
            self.assert_error(code, lambda: self.parse(body))

    def test_index_amount_absence_is_retained_without_fabrication(self):
        body = envelope(self.index)
        for point in body["data"]["items"][0]["points"]:
            del point["values"]["transaction_amount"]
        result = self.parse(body, self.index)
        self.assertTrue(all(row["amount"] is None for row in result["rows"]))
        self.assertEqual(result["amount_unit"], "unverified")

    def test_anomalous_names_are_preserved_but_not_used_as_identity(self):
        body = envelope(self.stock)
        raw_name = "\uf8f5" * 96
        body["data"]["items"][0]["points"][0]["values"]["security_name"] = raw_name
        result = self.parse(body)
        self.assertIsNone(result["rows"][0]["source_name"])
        self.assertEqual(result["rows"][0]["raw_security_name"], raw_name)
        self.assertEqual(result["name_diagnostics"], [{"row_index": 0, "code": "invalid_source_name"}])
        self.assertEqual(result["item_name_status"], "missing_source_name")
        self.assertEqual(result["rows"][1]["source_name"], "测试证券")

    def test_bad_envelopes_and_json_do_not_echo_server_text(self):
        for raw, code in ((b'{"ok":false,"error":"secret-server-message"}', "response_not_ok"),
                          (b'{"ok":true,"ok":false}', "duplicate_json_key"),
                          (b'{"ok":true,"data":NaN}', "nonfinite_json_constant"),
                          (b'\xff', "invalid_response_json")):
            self.assert_error(code, lambda: history.parse_history_response(
                raw, self.stock, "2022-08-24", "2022-08-25"))


class DailyCompatibilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Inspect and execute only the two pure/request methods we changed, with
        # synthetic transport/frame dependencies. No app module is imported.
        import pandas as pd
        source = (BACKEND / "app/data/tonghuasun_provider.py").read_text(encoding="utf-8-sig")
        tree = ast.parse(source)
        mapping = next(node for node in tree.body if isinstance(node, ast.FunctionDef)
                       and node.name == "tonghuasun_full_code")
        provider = next(node for node in tree.body if isinstance(node, ast.ClassDef)
                        and node.name == "TonghuasunMarketDataProvider")
        daily = next(node for node in provider.body if isinstance(node, ast.FunctionDef)
                     and node.name == "get_daily_bars")
        namespace = {"re": re, "pd": pd, "_ADJUSTMENT_VALUES": {"": 0, **history.ADJUSTMENTS},
                     "_CANDLE_FIELDS": history.FIELDS, "SOURCE": "tonghuasun.local.quotes.candle",
                     "SHARES_PER_HAND": 100.0, "TonghuasunDataError": RuntimeError,
                     "_candle_frame": lambda data, **kwargs: pd.DataFrame(data["fixture_rows"])}
        isolated = ast.Module(body=[ast.ImportFrom(module="__future__",
            names=[ast.alias(name="annotations")], level=0), mapping, daily], type_ignores=[])
        exec(compile(ast.fix_missing_locations(isolated), "isolated_provider_methods", "exec"), namespace)
        cls.mapping = staticmethod(namespace["tonghuasun_full_code"])
        cls.daily = staticmethod(namespace["get_daily_bars"])

    def test_explicit_exchanges_override_digit_inference_and_conflicts_reject(self):
        for symbol, expected in (("SH000300", "000300.SH"), ("SH000001", "000001.SH"),
                                 ("000300.SH", "000300.SH"), ("SZ000001", "000001.SZ"),
                                 ("BJ920000", "920000.BJ"), ("688981", "688981.SH")):
            self.assertEqual(self.mapping(symbol), expected)
        for symbol in ("SH000001.SZ", "USHA000300", "000001.US", "junk600000"):
            with self.assertRaises(ValueError):
                self.mapping(symbol)

    def test_daily_keeps_500_tail_and_hand_units_with_single_identifier(self):
        fixture_rows = [{"date": str(i), "volume": 123400.0} for i in range(501)]
        class SyntheticProvider:
            def _post_candles(self, payload):
                self.payload = payload
                return {"fixture_rows": fixture_rows}
        provider = SyntheticProvider()
        frame = self.daily(provider, "SH600011", days=1200)
        self.assertEqual(len(frame), 500)
        self.assertEqual(frame.iloc[0]["date"], "1")
        self.assertEqual(frame.iloc[0]["volume"], 1234.0)
        self.assertEqual(frame.attrs["volume_unit"], "hand")
        self.assertEqual(frame.attrs["adjustment_mode"], "qfq")
        self.assertEqual(provider.payload["security"], {"market": 1, "fullCode": "600011.SH"})
        self.assertNotIn("codes", provider.payload)
        self.assertEqual(provider.payload["limit"], 500)


if __name__ == "__main__":
    unittest.main(verbosity=2)
