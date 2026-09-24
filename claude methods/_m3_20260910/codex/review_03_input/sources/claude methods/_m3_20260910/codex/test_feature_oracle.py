"""Independent, hand-calculated checks for unchanged M3 feature definitions.

All observations are synthetic.  This checks the mathematical kernel rather
than claiming an unvalidated fixture has satisfied the full request contract.
Run only after static review of the currently delivered module.
"""
from __future__ import annotations

from datetime import date, timedelta
import importlib.util
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest


ROOT = Path(__file__).resolve().parents[3]
MODULE_PATH = ROOT / 'backend/app/research/m3_labels.py'
spec = importlib.util.spec_from_file_location('m3_feature_oracle_target', MODULE_PATH)
m = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = m
spec.loader.exec_module(m)


def bars():
    # Weekdays here are deliberately a declared mathematical fixture, not an
    # exchange calendar or a claim of actual observations on these dates.
    dates = []
    day = date(2023, 1, 2)
    while len(dates) < 301:
        if day.weekday() < 5:
            dates.append(day.isoformat())
        day += timedelta(days=1)
    rows = [SimpleNamespace(symbol='SYN910001', trade_date=d,
                            open=10.0, high=12.0, low=8.0, close=10.0,
                            volume=1_000_000.0, amount=10_000_000.0,
                            kind='price') for d in dates]
    rows[-1].close = 11.0
    rows[-1].volume = 2_000_000.0
    rows[-1].amount = 22_000_000.0
    return rows


class TestIndependentFeatureOracle(unittest.TestCase):
    def test_hand_calculated_terminal_bar(self):
        f = m.bar_features(bars(), 300)
        expected = {
            'close': 11.0, 'prev_close': 10.0, 'pct_change': .1,
            'return_20': .1, 'return_60': .1, 'return_120': .1,
            'ma20': 201 / 20, 'ma60': 601 / 60,
            'ma_spread_20_60': 2 / 601,
            'position_250': 3 / 4, 'high_250': 12.0,
            'close_to_high': 11 / 12,
            'drawdown_from_lookback_high': -1 / 12,
            'volume_ratio_20': 2.0, 'amount_20_mean_cny': 10_600_000.0,
        }
        for key, expected_value in expected.items():
            with self.subTest(feature=key):
                self.assertAlmostEqual(f[key], expected_value, places=10)

    def test_position_window_excludes_251st_bar(self):
        rows = bars()
        rows[50].low, rows[50].high = 1.0, 20.0
        self.assertAlmostEqual(m.bar_features(rows, 300)['position_250'], 3 / 4)
        rows[51].low, rows[51].high = 1.0, 20.0
        self.assertAlmostEqual(m.bar_features(rows, 300)['position_250'], 10 / 19)

    def test_volume_mean_uses_exactly_twenty_prior_bars(self):
        rows = bars()
        rows[279].volume = 100_000_000.0
        self.assertEqual(m.bar_features(rows, 300)['volume_ratio_20'], 2.0)
        rows[280].volume = 41_000_000.0
        # 19*1m + 41m = 60m; mean 3m, today's volume 2m.
        self.assertAlmostEqual(m.bar_features(rows, 300)['volume_ratio_20'], 2 / 3)

    def test_amount_mean_includes_today_but_not_21st_bar(self):
        rows = bars()
        rows[280].amount = 900_000_000.0
        self.assertEqual(m.bar_features(rows, 300)['amount_20_mean_cny'], 10_600_000.0)
        rows[281].amount = 30_000_000.0
        self.assertEqual(m.bar_features(rows, 300)['amount_20_mean_cny'], 11_600_000.0)

    def test_return_endpoints_use_k_price_intervals(self):
        for distance, key in [(20, 'return_20'), (60, 'return_60'), (120, 'return_120')]:
            with self.subTest(distance=distance):
                rows = bars()
                rows[300 - distance - 1].close = 4.0
                rows[300 - distance].close = 5.0
                self.assertAlmostEqual(m.bar_features(rows, 300)[key], 1.2)

    def test_kernel_ignores_offered_future_price_suffix(self):
        rows = bars()
        before = m.bar_features(rows, 300)
        # Offered future bars are deliberately extreme and must not be consumed
        # by this kernel call's explicit index. Full API validation is separate.
        rows.extend([SimpleNamespace(symbol='SYN910001', trade_date='2099-01-05',
                                     open=700.0, high=900.0, low=500.0, close=800.0,
                                     volume=1e12, amount=8e14, kind='price')])
        self.assertEqual(m.bar_features(rows, 300), before)

    def test_undefined_position_and_volume_denominator_remain_unknown(self):
        rows = bars()
        for row in rows:
            row.low = row.high = row.open = row.close = 10.0
            row.volume = row.amount = 0.0
        f = m.bar_features(rows, 300)
        self.assertIsNone(f['position_250'])
        self.assertIsNone(f['volume_ratio_20'])
        self.assertEqual(f['amount_20_mean_cny'], 0.0)
        self.assertTrue(f['zero_volume_session'])

    def test_return_needs_one_more_price_than_interval_length(self):
        rows = bars()
        for distance, key in [(20, 'return_20'), (60, 'return_60'), (120, 'return_120')]:
            with self.subTest(distance=distance):
                self.assertIsNone(m.bar_features(rows, distance - 1)[key])
                self.assertEqual(m.bar_features(rows, distance)[key], 0.0)


if __name__ == '__main__':
    unittest.main(verbosity=2)
