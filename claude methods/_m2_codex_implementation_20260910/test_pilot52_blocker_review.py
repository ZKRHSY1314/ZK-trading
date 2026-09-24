"""Offline interval boundaries and actual-data rejection; no source calls or DBs."""
import unittest
import review_pilot52_blockers_v2 as review
import review_pilot52_blockers_v3 as exchange_review


class GapReviewTests(unittest.TestCase):
    def test_exchange_observation_closes_gap_without_granting_eligibility(self):
        result = exchange_review.run()
        self.assertEqual(result["missing_status_counts"], {"issuer_confirmed_suspension": 297, "exchange_confirmed_suspension": 1})
        self.assertEqual(result["unresolved_keys"], [])
        lead = result["P4_failure"]["block_trade_lead"]
        self.assertTrue(lead["exchange_record_obtained"])
        self.assertTrue(lead["hypothesis_within_auction_price_range"])
        self.assertFalse(lead["source_total_scope_verified"])
        self.assertFalse(lead["correction_applied"])
        self.assertFalse(result["staging_eligible"])
        self.assertEqual(result["P4_failure"]["frozen_P4"], "FAIL")
        self.assertTrue(all(not gap["frozen_gate_exemption"] for gap in result["gap_ledger"]))

    def test_actual_resume_excludes_that_day_and_later_days(self):
        fact = {"start": "2024-08-29", "resume": "2024-09-02"}
        self.assertFalse(review.contains(fact, "2024-08-28"))
        self.assertTrue(review.contains(fact, "2024-08-30"))
        self.assertFalse(review.contains(fact, "2024-09-02"))
        self.assertFalse(review.contains(fact, "2024-09-03"))

    def test_open_suspension_is_bounded_by_actual_observation(self):
        fact = {"start": "2026-09-01", "resume": None, "confirmed_suspended_through": "2026-09-07"}
        self.assertTrue(review.contains(fact, "2026-09-04"))
        self.assertFalse(review.contains(fact, "2026-09-08"))
        self.assertFalse(review.contains({"start": "2026-09-01", "resume": None}, "2026-09-04"))

    def test_real_missing_inventory_and_p4_remain_rejected(self):
        result = review.run()
        self.assertEqual(result["missing_status_counts"], {"issuer_confirmed_suspension": 297, "unresolved_missing_bar": 1})
        self.assertEqual(result["unresolved_keys"], [{"symbol": "SH600110", "date": "2022-10-20"}])
        self.assertTrue(all(gap["frozen_gate_exemption"] is False for gap in result["gap_ledger"]))
        self.assertEqual(result["P4_failure"]["frozen_P4"], "FAIL")
        self.assertFalse(result["P4_failure"]["block_trade_lead"]["correction_applied"])
        self.assertFalse(result["M2_complete"])
        self.assertFalse(result["staging_eligible"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
