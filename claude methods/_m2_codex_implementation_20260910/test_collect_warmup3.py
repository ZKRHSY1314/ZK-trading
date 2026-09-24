import json
import unittest
from unittest.mock import patch
import collect_warmup3 as capture


class WarmupCaptureTests(unittest.TestCase):
    def test_wrong_review_pin_stops_before_runtime_and_http(self):
        with patch.object(capture.transport, "preflight") as preflight, patch.object(capture.base, "fetch") as fetch:
            with self.assertRaisesRegex(capture.base.StopCapture, "reviewed_plan_hash_mismatch"):
                capture.run("0" * 64)
            preflight.assert_not_called()
            fetch.assert_not_called()

    def test_only_approved_mature_shortfalls_and_completed_history_are_requested(self):
        plan = capture.plan()
        self.assertEqual({job["symbol"] for job in plan["jobs"]}, {"SZ002656", "SH600110", "SH600226"})
        self.assertEqual(len(plan["jobs"]), plan["max_attempts"])
        self.assertEqual(plan["retries"], 0)
        for job in plan["jobs"]:
            self.assertEqual(job["payload"]["period"], 7)
            self.assertEqual(job["payload"]["adjustment"], 0)
            self.assertEqual(job["payload"]["endTimeUtc"][:10], "2023-09-01")
            self.assertEqual(set(job["payload"]["security"]), {"hostFullCode"})

    def test_date_window_does_not_silently_accept_existing_later_history(self):
        source = capture.HERE / "remaining_capture_identity24"
        plan = json.loads((source / "plan.json").read_bytes())
        job = next(job for job in plan["jobs"] if job["symbol"] == "SH600110")
        raw = (source / f"response_{job['id']}.bin").read_bytes()
        parser = capture.parser_module()
        with self.assertRaises(parser.HistoryValidationError):
            parser.parse_history_response(raw, parser.SecuritySpec.stock("SH600110"), capture.START, capture.END)


if __name__ == "__main__":
    unittest.main(verbosity=2)
