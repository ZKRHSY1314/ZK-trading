import unittest
from proposed_semantic_checks import covered_inventory, auction_residual_check, run


class ProposedChecksTests(unittest.TestCase):
    def test_gap_label_cannot_hide_traded_conflict_or_extra_date(self):
        result = covered_inventory({1, 2}, {1, 3}, {1, 2})
        self.assertFalse(result["partition_complete"])
        self.assertEqual(result["conflicting_traded_suspensions"], [1])
        self.assertEqual(result["extra_observed"], [3])

    def test_unexplained_gap_cannot_pass(self):
        self.assertFalse(covered_inventory({1, 2}, {1}, set())["partition_complete"])

    def test_real_evidence_is_not_an_automatic_acceptance_exemption(self):
        result = run()
        self.assertTrue(result["coverage"]["partition_complete"])
        self.assertEqual(result["observed_rows"] + result["confirmed_suspension_keys"], 45935)
        self.assertEqual(result["block_trade_diagnostic"]["status"], "SCOPE_EVIDENCE_REQUIRED")
        self.assertFalse(result["M2_complete"])

    def test_block_trade_does_not_hide_scale_error(self):
        result = auction_residual_check("X", "2023-12-04", {"volume": 1610724, "amount": 1887685600, "low": "12.15", "high": "12.75"},
            {"symbol": "X", "date": "2023-12-04", "volume": 400000, "price": "9.25"}, scope_verified=True)
        self.assertEqual(result["status"], "FAIL")

    def test_wrong_date_rejected(self):
        with self.assertRaisesRegex(ValueError, "business_key"):
            auction_residual_check("X", "2023-12-04", {}, {"symbol": "X", "date": "2023-12-05"})


if __name__ == "__main__":
    unittest.main(verbosity=2)
