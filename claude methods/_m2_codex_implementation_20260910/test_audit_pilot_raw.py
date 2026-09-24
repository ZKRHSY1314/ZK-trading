"""Bounded tests for multi-day official scope and missing/listing keys; no app DB."""
import json
from pathlib import Path
import tempfile
import unittest

import audit_pilot_raw as audit


class OfficialPeriodTests(unittest.TestCase):
    days=['2026-06-09','2026-06-10','2026-06-11']

    def records(self):
        return {'SH600280':{('2026-06-09','2026-06-11','2026-06-11','60','600')}}

    def observed(self):
        return {'SH600280':{day:{'point_index':i,'raw_sha256':'a'*64,
            'volume':str((i+1)*10),'amount':str((i+1)*100)} for i,day in enumerate(self.days)}}

    def target(self,observed):
        return next(x for x in audit.compare_official(self.records(),observed,self.days) if x['symbol']=='SH600280')

    def test_three_day_reference_uses_all_three_days_not_final_day(self):
        result=self.target(self.observed())
        self.assertEqual(result['status'],'compared_same_interval')
        self.assertEqual(result['observed_dates'],self.days)
        self.assertEqual(result['comparison']['volume']['ths_period_sum_decimal'],'60')
        self.assertTrue(result['comparison']['amount']['exact_decimal_equal'])
        self.assertFalse(result['eligibility_granted'])

    def test_missing_middle_date_does_not_compare_partial_sum(self):
        observed=self.observed()
        del observed['SH600280']['2026-06-10']
        result=self.target(observed)
        self.assertEqual(result['status'],'missing_observed_dates')
        self.assertEqual(result['missing_dates'],['2026-06-10'])
        self.assertIsNone(result['comparison'])
        self.assertNotIn('observed_dates',result)

    def test_missing_symbol_is_not_zero_or_another_symbol(self):
        result=self.target({'SH600869':self.observed()['SH600280']})
        self.assertEqual(result['status'],'no_validated_raw_scope')
        self.assertIsNone(result['comparison'])
        self.assertEqual(result['missing_dates'],self.days)

    def test_single_day_comparison_does_not_include_adjacent_dates(self):
        record={'SH600869':{('2026-06-11','2026-06-11','2026-06-11','30','300')}}
        observed={'SH600869':self.observed()['SH600280']}
        result=next(x for x in audit.compare_official(record,observed,self.days) if x['symbol']=='SH600869')
        self.assertEqual(result['comparison']['volume']['ths_period_sum_decimal'],'30')
        self.assertEqual(result['observed_dates'],['2026-06-11'])

    def test_duplicate_summary_is_not_double_counted_and_broker_amount_ignored(self):
        row={'secCode':'600280','abnormalStart':'20260609','abnormalEnd':'20260611',
            'tradeDate':'20260611','secTxVolume':'60','secTxAmount':'600','branchTxAmtB':'99999'}
        records=audit.official_records({'result':[row], 'pageHelp':{'data':[row]}})
        self.assertEqual(len(records['SH600280']),1)
        result=next(x for x in audit.compare_official(records,self.observed(),self.days) if x['symbol']=='SH600280')
        self.assertTrue(result['comparison']['amount']['exact_decimal_equal'])

    def test_conflicting_official_period_cannot_be_selected_arbitrarily(self):
        records=self.records()
        records['SH600280'].add(('2026-06-11','2026-06-11','2026-06-11','30','300'))
        result=next(x for x in audit.compare_official(records,self.observed(),self.days) if x['symbol']=='SH600280')
        self.assertEqual(result['status'],'official_summary_missing_or_ambiguous')
        self.assertIsNone(result['comparison'])

    def test_listing_aware_domain_does_not_shrink_to_observed_dates(self):
        entry={'stratum':'ipo_in_window','list_date':'2023-09-05'}
        dates=['2022-08-24','2023-09-01','2023-09-04','2023-09-05','2023-09-06']
        expected=audit.expected_dates(entry,dates)
        self.assertEqual(expected,['2023-09-05','2023-09-06'])
        self.assertEqual(audit.window_counts(expected),{'research':2,'warmup':0})

    def test_qualification_embedded_request_does_not_require_unwritten_request_file(self):
        with tempfile.TemporaryDirectory() as root:
            directory=Path(root)/'qualification_capture'
            directory.mkdir()
            job={'id':3,'symbol':'SH600011','payload':{'period':7}}
            receipt={'reserved_at':'2026-09-09T17:12:20+00:00'}
            (directory/'attempt_3.json').write_text(json.dumps({'job':job,'reserved_at':receipt['reserved_at'],
                'state':'reserved_before_http'}),encoding='utf-8')
            evidence=audit.retained_request_evidence(directory,job,receipt)
            self.assertEqual(evidence['request_evidence_path'],str(directory/'attempt_3.json'))
            self.assertNotIn('request_sha256',evidence)
            with self.assertRaises(ValueError):
                audit.retained_request_evidence(directory,{**job,'symbol':'SH600869'},receipt)


if __name__=='__main__':
    unittest.main(verbosity=2)
