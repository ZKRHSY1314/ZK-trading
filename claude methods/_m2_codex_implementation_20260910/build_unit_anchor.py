"""Recompute official exchange vs retained THS absolute-unit observations offline.

This records exact decimal differences and a fixed binary32 representation
comparison. It does not infer representation types or certify all symbols from
two observations; the reviewed SDK field/market semantics remain a separate input.
"""
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import struct

HERE=Path(__file__).resolve().parent

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def reference_rows(value):
    if isinstance(value,dict):
        if value.get('secCode')=='600011' and 'secTxVolume' in value:
            yield value
        for item in value.values():yield from reference_rows(item)
    elif isinstance(value,list):
        for item in value:yield from reference_rows(item)

def same_binary32(left,right):
    return struct.pack('>f',float(left)).hex()==struct.pack('>f',float(right)).hex()

def build():
    raw_path=HERE/'qualification_capture/response_3.bin'
    receipt_path=HERE/'qualification_capture/completed_3.json'
    receipt=json.loads(receipt_path.read_bytes())
    if sha(raw_path)!=receipt['raw_sha256']:raise ValueError('raw_receipt_mismatch')
    body=json.loads(raw_path.read_bytes())
    security=body['data']['items'][0]['security']
    if security['hostFullCode']!='USHA600011' or security['fullCode']!='600011.SH':raise ValueError('source_identity_mismatch')
    observed={str(p['values']['date_time']):p['values'] for p in body['data']['items'][0]['points']}
    js_path=HERE/'unit_official/sse_public_query.js'
    script=js_path.read_text(encoding='utf-8-sig')
    # Review pointers are precise: dataPackage main1 headings, getTableDatas
    # volume/amount actions "/1000", and rendering of that action dividing 10000.
    markers=['成交量(万股/万份)','成交金额(万元)','"secTxVolume"','"secTxAmount"',
        'paramFunc == "/1000"','(parseFloat(value) / 10000).toFixed(2)']
    if not all(text in script for text in markers):raise ValueError('official_unit_rendering_evidence_changed')
    pins={str(p):sha(p) for p in [raw_path,receipt_path,js_path,Path(__file__)]}
    anchors=[]
    for day in ['20221129','20260529']:
        path=HERE/f'unit_official/sse_600011_{day}.json'
        source_receipt=path.with_name(path.name+'.receipt.json')
        meta=json.loads(source_receipt.read_bytes())
        if meta['status']!=200 or sha(path)!=meta['sha256']:raise ValueError('official_body_receipt_mismatch')
        if not meta['url'].startswith('https://query.sse.com.cn/marketdata/tradedata/queryTradeOpenInfo.do?'):
            raise ValueError('official_source_origin_mismatch')
        values=list(reference_rows(json.loads(path.read_bytes())))
        unique={(v['secTxVolume'],v['secTxAmount'],v['abnormalStart'],v['abnormalEnd'],v['tradeDate']) for v in values}
        if len(unique)!=1:raise ValueError('official_summary_not_unique')
        volume,amount,start,end,trade_day=unique.pop()
        if (start,end,trade_day)!=(day,day,day):raise ValueError('not_single_day_reference')
        target=observed[day]
        comparisons={}
        for field,reference,actual in [('volume',volume,target['transaction_volume']),('amount',amount,target['transaction_amount'])]:
            left,right=Decimal(reference),Decimal(str(actual))
            comparisons[field]={'official_decimal':str(left),'ths_decimal':str(right),
                'exact_decimal_equal':left==right,'difference_ths_minus_official':str(right-left),
                'binary32_equal':same_binary32(left,right),
                'official_binary32_hex':struct.pack('>f',float(left)).hex(),
                'ths_binary32_hex':struct.pack('>f',float(right)).hex()}
        anchors.append({'symbol':'SH600011','date':day,'source_url':meta['url'],
            'reference_sha256':sha(path),'raw_sha256':sha(raw_path),
            'official_volume_unit':'share','official_amount_unit':'CNY',
            'reference_scope':'single-day auction trades; exchange excludes block and after-hours fixed-price trades',
            'comparisons':comparisons})
        pins[str(path)]=sha(path);pins[str(source_receipt)]=sha(source_receipt)
    return {'schema':'m2.ths.unit_anchor.v1','created_at':datetime.now(timezone.utc).isoformat(),
        'input_pins':pins,'anchors':anchors,
        'all_anchor_fields_binary32_equal':all(c['binary32_equal'] for a in anchors for c in a['comparisons'].values()),
        'decimal_differences_retained':True,'binary32_source_type_proven_by_this_script':False,
        'source_unit_qualification_requires_reviewed_sdk_semantics':True,'all_symbol_eligibility_granted':False}

if __name__=='__main__':
    result=build()
    path=HERE/'unit_anchor_evidence.json'
    with path.open('x',encoding='utf-8') as handle:json.dump(result,handle,ensure_ascii=False,indent=2)
    print(json.dumps({'anchors':len(result['anchors']),'all_fields_binary32_equal':result['all_anchor_fields_binary32_equal'],
        'sha256':sha(path),'all_symbol_eligibility_granted':False}))
