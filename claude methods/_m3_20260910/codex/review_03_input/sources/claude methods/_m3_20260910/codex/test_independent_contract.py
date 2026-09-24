"""Codex adversarial contract checks. All observations/cases are SYNTHETIC.

This is independent review evidence, not a real case library or a policy adopted
by either reviewer. Run only after the delivered module is pinned and reviewed.
"""
import copy
from dataclasses import replace
from datetime import date, timedelta
import importlib.util
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[3]
MODULE = ROOT / 'backend/app/research/m3_labels.py'
spec = importlib.util.spec_from_file_location('codex_reviewed_m3_labels', MODULE)
m = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = m
spec.loader.exec_module(m)


def fixture(symbol='SYN000001', count=270):
    # Artificial daily sequence with bounded flat prices and explicit provenance.
    start = date(2024, 1, 1)
    days = []
    while len(days) < count:
        if start.weekday() < 5:
            days.append(start.isoformat())
        start += timedelta(days=1)
    return [m.Observation(symbol=symbol, trade_date=day,
            kind='price', available_at=m.close_time(day).isoformat(),
            source_ref=f'SYNTHETIC_ONLY:{symbol}:{i}', open=10.0, high=11.0, low=9.0,
            close=10.0, volume=2_000_000.0, amount=20_000_000.0) for i, day in enumerate(days)]


def request(**changes):
    rows = fixture()
    values = dict(symbol='SYN000001', observations=rows,
                  cutoff=m.Cutoff(rows[-1].trade_date, rows[-1].available_at), synthetic=True)
    values.update(changes)
    return m.LabelRequest(**values)


def summary(symbol, day, selection='non_candidate', episode=None):
    return dict(episode_id=episode or 'SYNTHETIC_ONLY:' + symbol + ':' + day,
                symbol=symbol, decision_date=day, policy_hash=m.POLICY_HASH,
                selection=selection, phase='accumulation' if selection == 'candidate' else 'markup',
                liquidity_band='L1_thin', regime='range', amount_20_mean_cny=20_000_000.0,
                synthetic=True)


class IndependentContract(unittest.TestCase):
    def test_matching_duplicate_record_does_not_meet_three_control_minimum(self):
        p = summary('SYN000001', '2024-09-01', 'candidate')
        c = summary('SYN000002', p['decision_date'])
        result = m.match_controls(p, [c] * 5, {p['decision_date']: 100})
        self.assertTrue(result['unmatched'], 'five copies of one control are one distinct control')
        self.assertLessEqual(result['control_count'], 1)

    def test_matching_same_control_symbol_on_five_dates_is_not_five_controls(self):
        p = summary('SYN000001', '2024-09-05', 'candidate')
        days = [f'2024-09-0{i}' for i in range(1, 6)]
        result = m.match_controls(p, [summary('SYN000002', d) for d in days], dict(zip(days, range(5))))
        self.assertTrue(result['unmatched'], 'one security must not satisfy 3-5 distinct controls')

    def test_matching_mixed_policy_not_selected(self):
        p = summary('SYN000001', '2024-09-01', 'candidate')
        c = summary('SYN000002', p['decision_date'])
        c['policy_hash'] = 'different-policy'
        try:
            result = m.match_controls(p, [c], {p['decision_date']: 100})
        except m.LabelInputError:
            return
        self.assertEqual(result['control_count'], 0)

    def test_matching_later_decision_not_available_to_positive_cutoff(self):
        p = summary('SYN000001', '2024-09-01', 'candidate')
        c = summary('SYN000002', '2024-09-02')
        result = m.match_controls(p, [c], {'2024-09-01': 100, '2024-09-02': 101})
        self.assertEqual(result['control_count'], 0, 'the positive cutoff cannot know tomorrow control labels')

    def test_episode_identity_binds_benchmark_that_changes_regime(self):
        base = request(benchmark_symbol='SYN000999', benchmark_observations=fixture('SYN000999'),
                       universe_coverage_on_decision_date=1.0)
        b = list(base.benchmark_observations)
        b[-1] = replace(b[-1], open=12.0, high=13.0, low=11.0, close=12.0, amount=24_000_000.0)
        a = m.generate_labels(base)
        z = m.generate_labels(replace(base, benchmark_observations=b))
        self.assertNotEqual(a['labels']['regime'], z['labels']['regime'])
        self.assertNotEqual(a['episode_id'], z['episode_id'], 'different decision evidence needs different identity')

    def test_episode_identity_binds_security_context_that_changes_phase(self):
        base = request()
        known = m.SecurityContext(corporate_action_status='known', known_ex_dates=(base.cutoff.decision_date,))
        a, b = m.generate_labels(base), m.generate_labels(replace(base, security=known))
        self.assertNotEqual(a['labels']['phase'], b['labels']['phase'])
        self.assertNotEqual(a['episode_id'], b['episode_id'])

    def test_late_benchmark_stays_unknown_at_decision_cutoff(self):
        b = fixture('SYN000999')
        b[-1] = replace(b[-1], available_at='2026-09-10T00:00:00+08:00')
        out = m.generate_labels(request(benchmark_symbol='SYN000999', benchmark_observations=b,
                                        universe_coverage_on_decision_date=1.0))
        self.assertEqual(out['labels']['regime']['regime'], 'unknown')

    def test_invalid_context_enum_cannot_remove_adjustment_gate(self):
        try:
            m.generate_labels(request(security=m.SecurityContext(corporate_action_status='KNOWN',
                              known_ex_dates=('2024-09-26',))))
        except m.LabelInputError:
            return
        self.fail('unknown enum accepted as a normal context')

    def test_invalid_coverage_is_rejected_not_known_market_regime(self):
        for value in [True, float('nan'), 1.5, -1]:
            with self.subTest(value=value):
                with self.assertRaises(m.LabelInputError):
                    m.generate_labels(request(benchmark_symbol='SYN000999',
                        benchmark_observations=fixture('SYN000999'), universe_coverage_on_decision_date=value))

    def test_missing_decision_bar_cannot_label_current_candidate(self):
        rows = fixture()
        out = m.generate_labels(request(observations=rows[:-1]))
        self.assertEqual(out['labels']['selection']['label'], 'indeterminate')

    def test_duplicate_cutoffs_do_not_create_three_session_episode(self):
        out = m.generate_labels(request())
        try:
            episodes = m.build_episodes([out, out, out])
        except m.LabelInputError:
            return
        self.assertFalse(any(e['meets_min_sessions'] for e in episodes))

    def test_episode_end_selection_is_current_end_not_first_member(self):
        out = m.generate_labels(request())
        end = copy.deepcopy(out)
        end['cutoff']['decision_date'] = (date.fromisoformat(out['cutoff']['decision_date']) + timedelta(days=3)).isoformat()
        end['episode_id'] = 'SYNTHETIC_ONLY:end'
        end['labels']['selection']['label'] = 'non_candidate'
        episodes = m.build_episodes([out, end])
        self.assertEqual(episodes[0]['selection_at_end'], 'non_candidate')

    def test_review_without_any_evidence_cannot_be_independently_reviewed(self):
        out = m.generate_labels(request())
        for who in ['synthetic_reviewer_A', 'synthetic_reviewer_B']:
            try:
                out = m.attach_review(out, m.ReviewRecord(who, 'agent', '2026-09-10T06:00:00Z', 'positive', ()))
            except m.LabelInputError:
                return
        self.assertNotEqual(out['review']['status'], 'independently_reviewed')

    def test_review_is_bound_to_specific_case_and_evidence_version(self):
        a = m.generate_labels(request())
        rows = fixture(count=269)
        b = m.generate_labels(request(observations=rows,
            cutoff=m.Cutoff(rows[-1].trade_date, rows[-1].available_at)))
        review = m.ReviewRecord('synthetic_reviewer_A', 'agent', '2026-09-10T06:00:00Z',
                               'positive', ('SYNTHETIC_ONLY:review-of:' + a['episode_id'],))
        try:
            m.attach_review(b, review)
        except m.LabelInputError:
            return
        self.fail('review object has no enforced episode/policy/evidence binding')

    def test_holdout_unknown_purpose_cannot_claim_protected(self):
        try:
            result = m.guard_final_holdout([{'decision_date': '2026-03-01'}], 'target_counts')
        except m.LabelInputError:
            return
        self.assertFalse(result['holdout_protected'], 'unrecognized purpose must not bypass holdout gate')

    def test_mutable_policy_export_cannot_change_labels_under_same_hash(self):
        original = copy.deepcopy(m.POLICY)
        before = m.generate_labels(request())
        try:
            doc = m.policy_document()
            doc['policy']['phase_rules']['accumulation']['position_250_lt'] = -1
            try:
                after = m.generate_labels(request())
            except m.LabelInputError:
                return
            if after['labels'] != before['labels']:
                self.assertNotEqual(after['policy_hash'], before['policy_hash'], 'policy mutation retained old hash')
        finally:
            m.POLICY.clear()
            m.POLICY.update(original)

    def test_known_action_does_not_emit_unadjusted_price_stop(self):
        base = request()
        rows = base.observations
        pos = m.PositionState(base.symbol, m.POLICY_HASH, rows[-4].trade_date,
                              rows[-3].trade_date, 12.0)
        out = m.generate_labels(replace(base, position_state=pos,
            security=m.SecurityContext(corporate_action_status='known', known_ex_dates=(rows[-2].trade_date,))))
        self.assertEqual(out['labels']['phase']['label'], 'indeterminate')
        self.assertNotIn(out['labels']['position_event']['label'], ['stop_event', 'exit_event'],
                         'known action across the holding basis must not become an unadjusted stop/target event')

    def test_position_reference_before_entry_is_rejected(self):
        base = request()
        rows = base.observations
        pos = m.PositionState(base.symbol, m.POLICY_HASH, rows[-4].trade_date,
                              rows[-10].trade_date, 10.0)
        with self.assertRaises(m.LabelInputError):
            m.generate_labels(replace(base, position_state=pos))


if __name__ == '__main__':
    unittest.main(verbosity=2)
