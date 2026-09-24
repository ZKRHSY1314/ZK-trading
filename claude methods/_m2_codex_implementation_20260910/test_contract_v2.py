"""Adversarial v2 checks against retained scope; no source/production access."""
import copy
from pathlib import Path
import unittest

import contract_v2 as c
import staging_v2 as s


class ContractTests(unittest.TestCase):
    def test_unknown_missing_extra_conflicting_and_duplicate_dates_rejected(self):
        c.partition(["a", "b"], ["a"], ["b"])
        for observed, halts in [(["a"], []), (["a", "c"], ["b"]), (["a", "b"], ["b"]),
                                (["a", "a"], ["b"]), (["a"], ["b", "b"])]:
            with self.subTest(observed=observed, halts=halts), self.assertRaises(c.old.StagingError):
                c.partition(["a", "b"], observed, halts)

    def test_unverified_wrong_date_wrong_units_and_impossible_residual_rejected(self):
        row = dict(symbol="BJ920006", trade_date="2023-12-04", volume=1610724,
                   amount=18876856, low=12.15, high=12.75)
        block = dict(symbol="BJ920006", date="2023-12-04", volume_shares=400000,
            price_CNY="9.25", amount_CNY="3700000", scope_evidence_verified=True, official_rule_sha256=c.PINS[c.PDF])
        self.assertTrue(c.p4_row(row, block).startswith("12.5353557045"))
        self.assertEqual(row["amount"], 18876856)
        cases = [(row, {**block, "scope_evidence_verified": False}), (row, {**block, "date": "2023-12-05"}),
            (row, {**block, "official_rule_sha256": "0"*64}), ({**row, "volume": 161072400}, block),
            (row, {**block, "amount_CNY": "1"}),
            ({**row, "volume": 400000}, block), ({**row, "amount": 0}, block)]
        for candidate, evidence in cases:
            with self.subTest(candidate=candidate, evidence=evidence), self.assertRaises(c.old.StagingError):
                c.p4_row(candidate, evidence)
        with self.assertRaises(c.old.StagingError):
            c.p4_row(row)

    def test_pinned_replay_has_exact_extension_and_old_failures_preserved(self):
        bundle, rows = c.build()
        self.assertEqual((bundle["rows_per_view"], bundle["research_rows"], bundle["warmup_rows"]), (45685,35943,9742))
        self.assertEqual([e["added"] for e in bundle["warmup_extension"]], [39,8,1])
        self.assertEqual(sum(e["overlap_numeric_checks"] for e in bundle["warmup_extension"]), 4212)
        self.assertEqual(bundle["listing_depth_shortfalls"], c.SHORT)
        self.assertEqual(bundle["original_contract_verdict"], "FAIL_preserved")
        self.assertFalse(bundle["strict_pit"] or bundle["live_trading"] or bundle["production_promoted"])
        self.assertEqual(len({(r["symbol"],r["trade_date"]) for r in rows}), 45685)

    def test_caller_cannot_supply_rewritten_or_incomplete_rows(self):
        run = s.StagingRunV2.__new__(s.StagingRunV2)
        run.replayed = [dict(symbol="SH600011",trade_date="2024-01-02",amount=123)]
        run.bundle = {"row_records_sha256": c.value_sha(run.replayed)}
        run.keys = {"SH600011": {"2024-01-02"}}
        for rows in ([], [dict(symbol="SH600011",trade_date="2024-01-02",amount=124)], run.replayed*2):
            with self.assertRaises(c.old.StagingError):
                run._rows(rows,{})

    def test_partial_success_report_never_accepts(self):
        with self.assertRaises(Exception):
            s.check_gate_acceptance("  P4 check PASS\n  RESULT: SUCCEEDED - all required gates PASS/NOT_APPLICABLE\n",0,"research",{})


if __name__ == "__main__":
    unittest.main(verbosity=2)
