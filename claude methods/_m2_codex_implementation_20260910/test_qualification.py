from copy import deepcopy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from qualification import absolute_unit_evidence, cash_forward_relation, compare_adjustments, m1_p4_numeric_consistency, volume_amount_envelope
from official import build_qualification_evidence as builder


class QualificationTests(unittest.TestCase):
    def row(self, **changes):
        row = dict(date='2026-01-05',open=10,high=11,low=9,close=10,volume=1000,amount=10000)
        row.update(changes)
        return row

    def test_scale_separation_is_not_unit_or_basis_certification(self):
        result = volume_amount_envelope([self.row()])
        self.assertEqual(result['necessary_envelope_at_scale_1'],'PASS')
        self.assertEqual(result['scale_results']['0.01']['outside'],1)
        self.assertFalse(result['absolute_units_verified'])
        self.assertFalse(result['eligibility_granted'])

    def test_equal_scaling_is_unidentifiable(self):
        a=volume_amount_envelope([self.row()])
        b=volume_amount_envelope([self.row(volume=10,amount=100)])
        self.assertEqual(a['scale_results'],b['scale_results'])
        self.assertFalse(b['absolute_units_verified'])

    def test_failures_not_fitted_away(self):
        for value in [True,None,'NaN',float('inf'),-1]:
            with self.subTest(value=value):
                result=volume_amount_envelope([self.row(volume=value)])
                self.assertEqual(len(result['invalid_rows']),1)
        self.assertEqual(volume_amount_envelope([self.row(amount=11001)])['scale_results']['1']['outside'],1)

    def test_zero_pair_not_evidence_and_asymmetric_zero_invalid(self):
        result=volume_amount_envelope([self.row(volume=0,amount=0)])
        self.assertEqual(result['necessary_envelope_at_scale_1'],'NOT_OBSERVED')
        self.assertEqual(len(volume_amount_envelope([self.row(amount=0)])['invalid_rows']),1)

    def test_boundary_decimal_exactness(self):
        result=volume_amount_envelope([self.row(low='0.1',high='0.3',volume=10,amount=3)])
        self.assertEqual(result['scale_results']['1']['inside'],1)

    def test_adjustment_key_mismatch_rejected(self):
        with self.assertRaises(ValueError):
            compare_adjustments({'0':{'2026-01-05':self.row()},'1':{},'2':{}})

    def test_adjustments_separate_prices_and_measures(self):
        day='2026-01-05'
        result=compare_adjustments({'0':{day:self.row()},'1':{day:self.row(close=9.5)},'2':{day:self.row(amount=9999)}})
        self.assertEqual(result['pairs']['0_vs_1']['price_difference_dates'],[day])
        self.assertEqual(result['pairs']['0_vs_1']['volume_amount_difference_dates'],[])
        self.assertEqual(result['pairs']['0_vs_2']['volume_amount_difference_dates'],[day])
        self.assertFalse(result['vendor_basis_verified'])

    def cash_fixture(self):
        before,exday='2026-01-05','2026-01-06'
        def prices(value):
            return self.row(open=value,high=value,low=value,close=value)
        return {'0':{before:prices(10),exday:prices(9.5)},
                '1':{before:prices(9.5),exday:prices(9.5)},
                '2':{before:prices(20),exday:prices(20)}}, [
                    dict(ex_date=exday,cash_per_share_CNY='0.5',document_sha256='a'*64)]

    def test_exact_cash_relation_is_not_standalone_eligibility(self):
        series,events=self.cash_fixture()
        result=cash_forward_relation(series,events)
        self.assertEqual(result['status'],'PASS')
        self.assertEqual(result['OHLC_checks'],8)
        self.assertEqual(result['boundaries'][0]['observed_cash_step'],'0.5')
        self.assertFalse(result['eligibility_granted'])

    def test_cash_dates_and_amounts_are_not_fitted(self):
        series,events=self.cash_fixture()
        events[0]['cash_per_share_CNY']='0.49'
        self.assertEqual(cash_forward_relation(series,events)['status'],'FAIL')
        events[0]['ex_date']='2026-01-07'
        with self.assertRaises(ValueError):cash_forward_relation(series,events)

    def test_official_document_hash_required(self):
        series,events=self.cash_fixture()
        events[0]['document_sha256']=''
        with self.assertRaises(ValueError):cash_forward_relation(series,events)

    def test_all_price_fields_checked(self):
        series,events=self.cash_fixture()
        series['1']['2026-01-05']['high']='9.5001'
        result=cash_forward_relation(series,events)
        self.assertEqual(result['status'],'FAIL')
        self.assertEqual(result['mismatches'][0]['field'],'high')

    def test_changed_measures_and_ignored_adjustment_rejected(self):
        series,events=self.cash_fixture()
        series['2']['2026-01-06']['volume']=1
        self.assertEqual(cash_forward_relation(series,events)['status'],'FAIL')
        series,events=self.cash_fixture()
        series['2']=series['0']
        self.assertEqual(cash_forward_relation(series,events)['status'],'FAIL')

    def test_duplicate_events_rejected(self):
        series,events=self.cash_fixture()
        with self.assertRaises(ValueError):cash_forward_relation(series,events+events)

    def test_original_p4_bounds_are_not_replaced_by_exact_diagnostic(self):
        row=self.row(low=10,high=10,amount=10001)
        self.assertEqual(volume_amount_envelope([row])['necessary_envelope_at_scale_1'],'FAIL')
        result=m1_p4_numeric_consistency([row])
        self.assertEqual(result['status'],'PASS')
        self.assertFalse(result['absolute_units_verified'])

    def test_original_p4_boundary_and_outside(self):
        self.assertEqual(m1_p4_numeric_consistency([self.row(low=10,high=10,amount=9800)])['status'],'PASS')
        self.assertEqual(m1_p4_numeric_consistency([self.row(low=10,high=10,amount=10200)])['status'],'PASS')
        self.assertEqual(m1_p4_numeric_consistency([self.row(low=10,high=10,amount=10201)])['status'],'FAIL')

    def test_original_p4_zero_and_missing_quarantined(self):
        self.assertEqual(m1_p4_numeric_consistency([self.row(volume=0,amount=0)])['status'],'UNKNOWN')
        self.assertEqual(m1_p4_numeric_consistency([self.row(amount=None)])['status'],'UNKNOWN')
        self.assertEqual(m1_p4_numeric_consistency([])['status'],'UNKNOWN')

    def unit_fixture(self):
        semantics=dict(volume_field_id=13,amount_field_id=19,plugin_numeric_transform='identity',
            volume_display='raw_divided_by_share_count_per_unit',share_count_per_unit={'USHA':100,'USZA':100,'USTM':100},
            amount_display='raw_with_magnitude_abbreviation_only')
        anchors=[dict(symbol='SH600011',date=day,reference_sha256='a'*64,raw_sha256='b'*64,
            official_volume_unit='share',official_amount_unit='CNY',
            comparisons={field:dict(official_decimal=official,ths_decimal=observed,binary32_equal=False)
                         for field,official,observed in [('volume','100000002','100000000'),('amount','1000000002','1000000000')]})
            for day in ['20221129','20260529']]
        return semantics,anchors

    def test_unit_combination_preserves_differences_without_precision_claim(self):
        semantics,anchors=self.unit_fixture()
        result=absolute_unit_evidence([self.row()], 'USHA',semantics,anchors)
        self.assertEqual(result['status'],'PASS')
        self.assertFalse(result['precision_model_used_for_qualification'])
        self.assertFalse(result['transport_dtype_proven'])
        self.assertFalse(result['eligibility_granted'])
        self.assertEqual(result['anchor_checks'][0]['difference_ths_minus_official'],'-2')

    def test_equal_amount_volume_scaling_cannot_pass_on_p4_alone(self):
        for multiplier,expected in [(10000,'0.0001'),(0.0001,'10000')]:
            with self.subTest(multiplier=multiplier):
                semantics,anchors=self.unit_fixture()
                rows=[self.row(volume=1000*multiplier,amount=10000*multiplier)]
                self.assertEqual(m1_p4_numeric_consistency(rows)['status'],'PASS')
                for anchor in anchors:
                    for comparison in anchor['comparisons'].values():
                        comparison['ths_decimal']=str(float(comparison['ths_decimal'])*multiplier)
                        comparison['binary32_equal']=True
                result=absolute_unit_evidence(rows,'USHA',semantics,anchors)
                self.assertEqual(result['status'],'FAIL')
                self.assertEqual(result['anchor_checks'][0]['best_multiplier_candidates'],[expected])

    def test_unit_static_chain_and_official_anchor_are_both_required(self):
        semantics,anchors=self.unit_fixture()
        semantics['plugin_numeric_transform']='divide_10000'
        self.assertEqual(absolute_unit_evidence([self.row()],'USHA',semantics,anchors)['status'],'FAIL')
        semantics,anchors=self.unit_fixture()
        self.assertEqual(absolute_unit_evidence([self.row()],'USHA',semantics,[])['status'],'UNKNOWN')

    def test_unit_stock_scope_does_not_claim_index_liquidity(self):
        semantics,anchors=self.unit_fixture()
        self.assertEqual(absolute_unit_evidence([self.row()],'USHI',semantics,anchors)['status'],'FAIL')

    def test_unit_reference_unit_and_hash_required(self):
        semantics,anchors=self.unit_fixture()
        anchors[0]['official_amount_unit']='wan_CNY'
        with self.assertRaises(ValueError):absolute_unit_evidence([self.row()],'USHA',semantics,anchors)
        semantics,anchors=self.unit_fixture()
        anchors[0]['reference_sha256']=''
        with self.assertRaises(ValueError):absolute_unit_evidence([self.row()],'USHA',semantics,anchors)

    def test_unit_precision_flags_cannot_change_decision(self):
        semantics,anchors=self.unit_fixture()
        first=absolute_unit_evidence([self.row()],'USHA',semantics,anchors)
        for anchor in anchors:
            for comparison in anchor['comparisons'].values():comparison['binary32_equal']=True
        second=absolute_unit_evidence([self.row()],'USHA',semantics,anchors)
        self.assertEqual(first,second)

    def test_unit_p4_contradiction_or_quarantine_still_blocks(self):
        semantics,anchors=self.unit_fixture()
        self.assertEqual(absolute_unit_evidence([self.row(amount=100000)],'USHA',semantics,anchors)['status'],'FAIL')
        self.assertEqual(absolute_unit_evidence([self.row(volume=0,amount=0)],'USHA',semantics,anchors)['status'],'FAIL')

    def test_duplicate_unit_anchor_is_not_extra_evidence(self):
        semantics,anchors=self.unit_fixture()
        with self.assertRaises(ValueError):absolute_unit_evidence([self.row()],'USHA',semantics,[anchors[0],anchors[0]])


class BuilderBindingTests(unittest.TestCase):
    def test_entrypoint_not_reused_transport_dependency(self):
        pins={'capture.py':'a'*64,'collect_remaining.py':'b'*64}
        self.assertEqual(builder.collector_identity('qualification',pins),('capture.py','a'*64))
        self.assertEqual(builder.collector_identity('remaining_pilot_raw_quarantine',pins),('collect_remaining.py','b'*64))

    def test_missing_or_ambiguous_entrypoint_rejected(self):
        with self.assertRaises(ValueError):builder.collector_identity('remaining_pilot_raw_quarantine',{'capture.py':'a'*64})
        with self.assertRaises(ValueError):builder.collector_identity('unknown',{'capture.py':'a'*64})
        with self.assertRaises(ValueError):builder.collector_identity('qualification',{'x/capture.py':'a'*64,'y/capture.py':'b'*64})

    def test_scope_needs_own_raw_receipt_preflight_and_producer(self):
        fields=('raw_body_sha256','capture_receipt_sha256','capture_producer_manifest_sha256','capture_preflight_sha256','collector_sha256','request_artifact_sha256')
        scope={field:hex(index+10)[2:]*64 for index,field in enumerate(fields)}
        artifacts=[{'sha256':value} for value in scope.values()]
        self.assertEqual(set(builder.complete_scope_references(scope,artifacts)),set(scope.values()))
        for missing in fields:
            with self.subTest(missing=missing):
                other=[row for row in artifacts if row['sha256']!=scope[missing]]+[{'sha256':'0'*64}]
                with self.assertRaises(ValueError):builder.complete_scope_references(scope,other)

    def test_replacing_reviewed_anchor_is_rejected_before_numeric_policy(self):
        original_here=builder.HERE
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            for name in ['unit_semantics_static_review.md','unit_semantics_static_verification.json']:
                (root/name).write_bytes((original_here/name).read_bytes())
            original=json.loads((original_here/'unit_anchor_evidence.json').read_bytes())
            for multiplier in [1.000001,10000,0.0001]:
                changed=deepcopy(original)
                for anchor in changed['anchors']:
                    for comparison in anchor['comparisons'].values():
                        comparison['ths_decimal']=str(float(comparison['ths_decimal'])*multiplier)
                (root/'unit_anchor_evidence.json').write_text(json.dumps(changed),encoding='utf-8')
                with patch.object(builder,'HERE',root):
                    with self.assertRaisesRegex(ValueError,'reviewed unit evidence changed'):builder.unit_inputs()

    def test_duplicate_evidence_json_keys_not_silently_accepted(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'evidence.json'
            path.write_text('{"ok":false,"ok":true}',encoding='utf-8')
            with self.assertRaisesRegex(ValueError,'duplicate JSON key'):builder.read(path)

if __name__ == '__main__':
    unittest.main()
