"""R3 independent checks with the final explicit prefix-review API.

The earlier 23-method source is preserved byte-for-byte, as delivered to Claude.
Only the valid fixture's review construction is adapted; rejection assertions
and their evidence mutations stay intact. All inputs remain invented in memory.
"""
from dataclasses import replace
import importlib.util
from pathlib import Path
import sys
import unittest

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('codex_r3_unbound_fixture', HERE / 'test_independent_r3.py')
previous = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = previous
spec.loader.exec_module(previous)
m = previous.m
original_fixture = previous.format_fixture


def bound_format_fixture():
    prefix, controls, match, cal, changed_prefix = original_fixture()
    req = previous.base.request('SH600011')
    bench = tuple(replace(b, symbol='SH000300', source_ref='syn:fixture-only-benchmark')
                  for b in req.benchmark_observations)
    req = replace(req, synthetic=False, calendar=cal, benchmark_symbol='SH000300',
                  benchmark_observations=bench,
                  universe=m.FrozenUniverse(frozenset(('SH600011', 'SH600110', 'SH600129', 'SH600162')),
                                            'syn:fixture-only-universe', '1' * 64))
    # Re-generate the exact unreviewed representative via the public API instead
    # of modifying a ledger or manufacturing a replacement record hash.
    rec = m.generate_labels(req)
    assert rec['record_hash'] == prefix[-1]['record_hash']
    prefix[-1] = rec
    proof = m.prefix_proof_for(prefix, cal, prefix[-1])
    assert proof is not None and proof['representative_record_hash'] == rec['record_hash']
    for who in ('syn:fixture-only-reviewer-a', 'syn:fixture-only-reviewer-b'):
        prefix[-1] = m.attach_review(prefix[-1], previous.base.review(
            prefix[-1], who, synthetic=False, case_prefix_hash=proof['prefix_hash']))
    return prefix, controls, match, cal, changed_prefix


previous.format_fixture = bound_format_fixture


class TestIndependentR3Bound(previous.TestIndependentR3Admission):
    def test_daily_reviews_alone_never_endorse_an_episode(self):
        prefix, controls, match, cal, _ = original_fixture()
        count = m.library_counts([*prefix, *controls], [match], cal)
        self.assertEqual(count['qualified_positives'], 0)
        self.assertEqual(count['disqualified_episodes'].get('review_not_bound_to_prefix'), 1)


if __name__ == '__main__':
    unittest.main(verbosity=2)
