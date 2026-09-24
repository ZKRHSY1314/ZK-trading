"""Independent R3 admission checks using invented, in-memory fixtures only.

The non-synthetic flags deliberately exercise the actual-format consumer path;
all prices, sources, identities of reviewers and executions remain SYN fixtures.
Nothing from these fixtures is saved as a real case or actual review.
"""
import copy
from dataclasses import replace
import importlib.util
from pathlib import Path
import sys
import unittest

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('codex_r2_fixture_for_r3', HERE / 'test_independent_r2.py')
base = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = base
spec.loader.exec_module(base)
m = base.m

# The benchmark supplement adds an explicit amount unit and requires both
# retained index units. Adapt fixture construction only; keep R2 assertions.
_r2_request = base.request


def request_r3(*args, **kwargs):
    req = _r2_request(*args, **kwargs)
    return replace(req, benchmark_observations=tuple(
        replace(b, volume_unit='not_applicable', amount_unit='not_applicable')
        for b in req.benchmark_observations))


base.request = request_r3


def format_fixture():
    """Three consecutive candidate decisions, three same-date controls."""
    symbols = ('SH600011', 'SH600110', 'SH600129', 'SH600162')
    universe = m.FrozenUniverse(frozenset(symbols), 'syn:fixture-only-universe', '1' * 64)
    cal = replace(base.CAL, source_ref='syn:fixture-only-real-format-calendar', synthetic=False)

    def req(symbol, end=269, changed_source=False):
        r = base.request(symbol, end=end)
        bench = tuple(replace(b, symbol='SH000300', source_ref='syn:fixture-only-benchmark')
                      for b in r.benchmark_observations)
        obs = tuple(replace(b, source_ref='syn:fixture-only-changed-source:'+b.trade_date)
                    for b in r.observations) if changed_source else r.observations
        if symbol != symbols[0]:
            obs = (*obs[:-1], replace(obs[-1], high=13.5, close=13., volume=3_000_000., amount=39_000_000.))
        return replace(r, observations=obs, benchmark_symbol='SH000300', benchmark_observations=bench,
                       synthetic=False, calendar=cal, universe=universe)

    prefix = [m.generate_labels(req(symbols[0], i)) for i in (267, 268, 269)]
    for who in ('syn:fixture-only-reviewer-a', 'syn:fixture-only-reviewer-b'):
        prefix[-1] = m.attach_review(prefix[-1], base.review(prefix[-1], who, synthetic=False))
    controls = [m.generate_labels(req(symbol)) for symbol in symbols[1:]]
    match = m.match_controls(prefix[-1], controls)
    assert not match['unmatched'] and match['control_count'] == 3
    assert all(r['labels']['phase']['label'] == m.PHASE_ACCUMULATION for r in prefix)
    changed_prefix = [m.generate_labels(req(symbols[0], i, True)) for i in (267, 268)]
    return prefix, controls, match, cal, changed_prefix


class TestIndependentR3Admission(base.TestIndependentR2Consumers):
    def test_single_decision_cannot_establish_minimum_episode_duration(self):
        prefix, controls, match, cal, _ = format_fixture()
        # R3's declared API requires the resolved control cores supplied in memory.
        count = m.library_counts([prefix[-1], *controls], [match], cal)
        self.assertEqual(count['qualified_positives'], 0)
        self.assertEqual(count['effective_dependence_groups'], 0)

    def test_complete_format_fixture_counts_one_episode(self):
        prefix, controls, match, cal, _ = format_fixture()
        count = m.library_counts([*prefix, *controls], [match], cal)
        self.assertEqual(count['qualified_positives'], 1,
                         'A valid actual-format fixture must pass the same path as rejection controls')
        self.assertEqual(count['unique_controls'], 3)
        self.assertEqual(count['control_uses'], 3)
        self.assertFalse(count['target_met'])

    def test_review_cannot_silently_move_to_another_episode_prefix(self):
        prefix, controls, match, cal, changed_prefix = format_fixture()
        first = m.library_counts([*prefix, *controls], [match], cal)
        self.assertEqual(first['qualified_positives'], 1)
        # Preserve the exact reviewed representative, all its evidence, the
        # ledgers and match. Substitute two independently generated earlier
        # member records from a different source. Their cores are valid, but
        # the old review cannot endorse a newly reconstructed episode proof.
        for original, changed in zip(prefix[:2], changed_prefix):
            self.assertNotEqual(original['record_hash'], changed['record_hash'])
        try:
            after = m.library_counts([*changed_prefix, prefix[-1], *controls], [match], cal)
        except m.LabelInputError:
            return
        if after['qualified_positives']:
            self.assertEqual(first['qualified_episodes'][0]['prefix_hash'],
                             after['qualified_episodes'][0]['prefix_hash'],
                             'An unchanged review was rebound to a different prefix without new review evidence')

    def test_missing_middle_session_does_not_qualify(self):
        prefix, controls, match, cal, _ = format_fixture()
        count = m.library_counts([prefix[0], prefix[-1], *controls], [match], cal)
        self.assertEqual(count['qualified_positives'], 0)

    def test_unavailable_coverage_value_cannot_change_consumed_identity(self):
        req = base.request()
        a = replace(req, universe_coverage_on_decision_date=m.Coverage(.3, 'syn:future-a', '2026-09-10T00:00:00+00:00'))
        b = replace(req, universe_coverage_on_decision_date=m.Coverage(.9, 'syn:future-b', '2026-09-10T00:00:00+00:00'))
        ra, rb = m.generate_labels(a), m.generate_labels(b)
        self.assertEqual(ra['labels'], rb['labels'])
        self.assertEqual(ra['record_hash'], rb['record_hash'])
        self.assertEqual(ra['episode_id'], rb['episode_id'])

    def test_declared_decision_inputs_must_recompute_the_fingerprint(self):
        record = m.generate_labels(base.request())
        record['identity']['decision_inputs']['stock_rows'] = '0' * 64
        record['record_hash'] = m.record_hash(record)
        # This is an internally inconsistent serializer output with a valid
        # outer checksum, not a request to prove external provenance by hash.
        with self.assertRaises(m.LabelInputError):
            m.verify_record(record)

    def test_index_level_with_retained_m2_units_generates_price_only_regime(self):
        req = base.request()
        def index_rows(volume, amount):
            return tuple(replace(b, open=3000., high=3100., low=2900., close=3000.,
                                 volume=volume, amount=amount, volume_unit='not_applicable', amount_unit='not_applicable')
                         for b in req.benchmark_observations)
        first = m.generate_labels(replace(req, benchmark_observations=index_rows(2_000_000., 20_000_000.)))
        second = m.generate_labels(replace(req, benchmark_observations=index_rows(3_000_000., 95_000_000.)))
        self.assertEqual(first['labels']['regime']['regime'], 'range')
        self.assertEqual(first['labels']['regime'], second['labels']['regime'])
        self.assertFalse(first['pit']['training_eligible'])

    def test_benchmark_role_does_not_bypass_ohlc_or_availability(self):
        req = base.request()
        rows = tuple(replace(b, volume_unit='not_applicable') for b in req.benchmark_observations)
        for changes in ({'low': 0.}, {'open': 100.}, {'available_at': '2022-12-01T00:00:00+08:00'}):
            with self.subTest(changes=changes):
                altered = (*rows[:-1], replace(rows[-1], **changes))
                with self.assertRaises(m.LabelInputError):
                    m.generate_labels(replace(req, benchmark_observations=altered))

    def test_stock_cannot_use_index_units_or_escape_stock_vwap(self):
        req = base.request()
        for changes in ({'volume_unit': 'not_applicable'}, {'amount': 100_000_000.}):
            with self.subTest(changes=changes):
                altered = (*req.observations[:-1], replace(req.observations[-1], **changes))
                with self.assertRaises(m.LabelInputError):
                    m.generate_labels(replace(req, observations=altered))


if __name__ == '__main__':
    unittest.main(verbosity=2)
