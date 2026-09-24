"""Independent extension invariance over already validated real-format inputs.

No SQLite and no case reviews. Reads the retained first development output and
uses its exact cutoff-bound cores to exercise the current reader packet builder.
"""
import copy
import gzip
import importlib.util
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[3]
RUN = ROOT / 'claude methods/_m3_20260910/claude_02/runs/dev_run_01'
spec = importlib.util.spec_from_file_location('reader_packet_extension_target', ROOT/'backend/app/research/m3_frozen_reader.py')
r = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = r
spec.loader.exec_module(r)


class TestPacketExtension(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.m = r.load_labels()
        eps = json.loads((RUN/'episodes.json').read_text(encoding='utf-8'))
        cls.item = next(p for p in eps['packets'] if p['exclusion'] is None)
        cls.ep = next(e for e in eps['episodes'] if e['episode_key'] == cls.item['episode_key'])
        packet = json.loads((RUN/'packets'/(cls.item['episode_key']+'.json')).read_text(encoding='utf-8'))
        cls.proof = packet['prefix_proof']
        cls.symbol = packet['symbol']
        cls.day = packet['representative']['decision_date']
        cls.grade = packet['uncertainties']['listing_source_grade']
        records = {}
        for p in sorted((RUN/'chronology').glob('*.jsonl.gz')):
            rows = [json.loads(x)['record'] for x in gzip.decompress(p.read_bytes()).decode('utf-8').splitlines()]
            records[p.name.removesuffix('.jsonl.gz')] = {x['cutoff']['decision_date']:x for x in rows}
        cls.rep = records[cls.symbol][cls.day]
        cls.prefix = [records[cls.symbol][x['decision_date']] for x in packet['members']]
        cls.pool = [rows[cls.day] for s,rows in sorted(records.items()) if s != cls.symbol and cls.day in rows]

    def build(self, episode, proof=None, prefix=None, pool=None):
        return r.build_cutoff_packet(self.m, episode, proof or self.proof, prefix or self.prefix,
            self.rep, self.pool if pool is None else pool, self.grade, self.symbol, False)

    def test_positive_path_produces_three_to_five_controls(self):
        p = self.build(self.ep)
        self.assertEqual(len(p['members']), 3)
        self.assertIsNone(p['exclusion'])
        self.assertFalse(p['match']['unmatched'])
        self.assertTrue(3 <= p['match']['control_count'] <= 5)
        self.assertEqual(p['reviews'], [])
        self.assertEqual(p['cutoff_packet_hash'], r.cutoff_packet_hash(p))

    def test_later_episode_end_status_and_selection_path_cannot_change_packet(self):
        baseline = self.build(self.ep)
        changed = copy.deepcopy(self.ep)
        changed.update(end='2025-03-31',status='open_censored',closed_reason=None,
            eligibility_changes=999,candidate_sessions=999,selection_at_end='indeterminate',
            selection_path=[{'date':self.ep['start'],'selection':'candidate'},
                            {'date':'2025-03-31','selection':'indeterminate'}])
        self.assertNotEqual(changed, self.ep)
        self.assertEqual(self.build(changed), baseline)
        for key in ('known_end_so_far','end','status','selection_path','eligibility_changes','closed_reason'):
            self.assertNotIn(key, baseline)

    def test_changed_prefix_binding_is_rejected(self):
        prefix = copy.deepcopy(self.prefix)
        prefix[0]['record_hash'] = '0'*64
        with self.assertRaises(r.ReaderError):
            self.build(self.ep, prefix=prefix)

    def test_later_dated_control_is_rejected(self):
        pool = copy.deepcopy(self.pool)
        pool[0]['cutoff']['decision_date'] = '2025-03-31'
        with self.assertRaises(r.ReaderError):
            self.build(self.ep, pool=pool)


if __name__ == '__main__':
    unittest.main(verbosity=2)
