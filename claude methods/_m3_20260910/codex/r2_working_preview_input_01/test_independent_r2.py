"""Synthetic-only consumer-boundary tests for the M3-01-R2 API.

These are independent checks, not actual reviews or real case-library records.
No file below is owned by Claude. Run only against a statically inspected module.
"""
from __future__ import annotations

import copy
from dataclasses import replace
from datetime import date, timedelta
import importlib.util
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location('m3_independent_r2_target', ROOT / 'backend/app/research/m3_labels.py')
m = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = m
spec.loader.exec_module(m)

days = []
day = date(2023, 1, 2)
while len(days) < 300:
    if day.weekday() < 5:
        days.append(day.isoformat())
    day += timedelta(days=1)
CAL = m.SessionCalendar(tuple(days), 'syn:independent-calendar', '2022-12-01T00:00:00+08:00', True)


def request(symbol='SYN001001', end=269, **overrides):
    def observations(code):
        return tuple(m.Observation(code, d, 'price', d+'T15:00:00+08:00',
                                   f'syn:independent:{code}:{d}', 10., 11., 9., 10.,
                                   2_000_000., 20_000_000.) for d in days[:end+1])
    args = dict(symbol=symbol, observations=observations(symbol),
                cutoff=m.Cutoff(days[end], days[end]+'T16:00:00+08:00'),
                calendar=CAL, synthetic=True,
                benchmark_symbol='SYN900001', benchmark_observations=observations('SYN900001'),
                universe_coverage_on_decision_date=m.Coverage(1., 'syn:coverage', '2022-12-01T00:00:00+08:00'))
    args.update(overrides)
    return m.LabelRequest(**args)


def review(record, who, verdict='positive', **overrides):
    args = dict(reviewer_id=who, reviewer_kind='agent', reviewed_at='2026-09-10T07:00:00+00:00',
                verdict=verdict, evidence_refs=('syn:fixture-only-case-evidence',),
                execution_ref='syn:fixture-only-execution:'+who,
                case_episode_id=record['episode_id'], case_record_hash=record['record_hash'],
                case_policy_hash=record['policy_hash'], synthetic=True)
    args.update(overrides)
    return m.ReviewRecord(**args)


def two_reviews(record):
    for who in ('syn-reviewer-a', 'syn-reviewer-b'):
        record = m.attach_review(record, review(record, who))
    return record


class TestIndependentR2Consumers(unittest.TestCase):
    def test_fixture_is_candidate_and_every_case_is_synthetic(self):
        rec = m.generate_labels(request())
        self.assertEqual(rec['labels']['selection']['label'], 'candidate')
        self.assertTrue(rec['synthetic'])
        self.assertFalse(rec['pit']['training_eligible'])
        self.assertFalse(m.library_counts([rec], [], CAL)['target_met'])

    def test_unmodified_review_append_preserves_core(self):
        rec = m.generate_labels(request())
        reviewed = two_reviews(rec)
        self.assertEqual(reviewed['record_hash'], rec['record_hash'])
        self.assertEqual(len(reviewed['review_ledger']['entries']), 2)
        self.assertEqual(len(rec['review_ledger']['entries']), 0)
        self.assertEqual(m.library_counts([reviewed], [], CAL)['qualified_positives'], 0)

    def test_transplanted_valid_ledger_cannot_accept_a_new_case_review(self):
        first = two_reviews(m.generate_labels(request()))
        other = m.generate_labels(request('SYN001002'))
        other['review_ledger'] = copy.deepcopy(first['review_ledger'])
        # The other core is still valid: this simulates joining the wrong ledger
        # to a real record, without altering a record or manufacturing a hash.
        self.assertEqual(m.record_hash(other), other['record_hash'])
        with self.assertRaises(m.LabelInputError):
            m.attach_review(other, review(other, 'syn-reviewer-c'))

    def test_library_count_rejects_tampered_ledger(self):
        rec = two_reviews(m.generate_labels(request()))
        rec['review_ledger']['entries'][0]['execution_ref'] = ''
        with self.assertRaises(m.LabelInputError):
            m.library_counts([rec], [], CAL)

    def test_library_count_rejects_duplicate_case_records(self):
        rec = two_reviews(m.generate_labels(request()))
        try:
            count = m.library_counts([rec, copy.deepcopy(rec)], [], CAL)
        except m.LabelInputError:
            return
        self.assertLessEqual(count['independently_reviewed'], 1,
                             'Duplicating a reviewed case must not duplicate the review count')

    def test_compact_summary_cannot_relabel_candidate_controls(self):
        positive = m.generate_labels(request())
        forged = []
        for i in range(3):
            rec = m.generate_labels(request('SYN00100'+str(i+2)))
            self.assertEqual(rec['labels']['selection']['label'], 'candidate')
            summary = m.case_summary(rec)
            summary['selection'] = 'non_candidate'
            forged.append(summary)
        try:
            match = m.match_controls(positive, forged)
        except m.LabelInputError:
            return
        self.assertTrue(match['unmatched'], 'A retained hash is not proof of altered summary fields')

    def test_compact_summary_cannot_invent_record_hash(self):
        rec = m.generate_labels(request())
        summary = m.case_summary(rec)
        summary['record_hash'] = 'z' * 64
        with self.assertRaises(m.LabelInputError):
            m.case_summary(summary)

    def test_superseding_an_already_superseded_review_cannot_fork_current_verdict(self):
        rec = m.generate_labels(request())
        rec = m.attach_review(rec, review(rec, 'syn-reviewer-a'))
        initial = rec['review_ledger']['entries'][0]['entry_hash']
        rec = m.attach_review(rec, review(rec, 'syn-reviewer-a', 'ambiguous',
                                         supersedes=initial, supersede_reason='syn:corrected-reading',
                                         reviewed_at='2026-09-10T07:01:00+00:00'))
        with self.assertRaises(m.LabelInputError):
            m.attach_review(rec, review(rec, 'syn-reviewer-a', 'negative',
                                       supersedes=initial, supersede_reason='syn:stale-base',
                                       reviewed_at='2026-09-10T07:02:00+00:00'))

    def test_superseding_review_must_be_later_than_original(self):
        rec = m.generate_labels(request())
        rec = m.attach_review(rec, review(rec, 'syn-reviewer-a'))
        initial = rec['review_ledger']['entries'][0]['entry_hash']
        with self.assertRaises(m.LabelInputError):
            m.attach_review(rec, review(rec, 'syn-reviewer-a', 'ambiguous',
                                       supersedes=initial, supersede_reason='syn:impossible-time',
                                       reviewed_at='2026-09-09T07:00:00+00:00'))

    def test_session_close_reference_cannot_be_available_before_reference_date(self):
        sec = m.SecurityContext(corporate_action_status=m.CA_NONE_VERIFIED,
                                evidence_refs=('syn:no-actions',),
                                facts_available_at='2022-12-01T00:00:00+08:00')
        pos = m.PositionState('SYN001001', m.POLICY_HASH, days[260], days[261], 10.,
                              reference_basis='session_close', evidence_ref='syn:reference-close',
                              available_at='2022-12-01T00:00:00+08:00')
        with self.assertRaises(m.LabelInputError):
            m.generate_labels(request(security=sec, position_state=pos))

    def test_non_consumed_context_does_not_change_decision_identity(self):
        late_a = m.SecurityContext(st_status='st', evidence_refs=('syn:late-a',),
                                   facts_available_at='2026-09-10T00:00:00+00:00')
        late_b = replace(late_a, st_status='not_st', evidence_refs=('syn:late-b',))
        first = m.generate_labels(request(security=late_a))
        second = m.generate_labels(request(security=late_b))
        self.assertFalse(first['context_availability']['usable'])
        self.assertFalse(second['context_availability']['usable'])
        self.assertEqual(first['labels'], second['labels'])
        self.assertEqual(first['episode_id'], second['episode_id'],
                         'Offered-only facts must not enter immutable consumed decision identity')

    def test_future_stock_suffix_remains_invariant(self):
        original = request()
        extended = request(end=280)
        extended = replace(extended, cutoff=original.cutoff)
        first, second = m.generate_labels(original), m.generate_labels(extended)
        self.assertEqual(first['record_hash'], second['record_hash'])
        self.assertEqual(first['episode_id'], second['episode_id'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
