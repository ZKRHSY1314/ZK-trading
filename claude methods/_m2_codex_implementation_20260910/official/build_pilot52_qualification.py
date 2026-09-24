"""Offline evidence assembly. Reads retained bytes only; never performs HTTP/DB I/O.

This is intentionally independent of the production history parser. A later
staging writer must replay that parser and independently review this bundle.
"""
from datetime import datetime, timezone
from decimal import Decimal
from hashlib import sha256
import csv
import html
import json
from pathlib import Path
import re
import sys

OFFICIAL=Path(__file__).resolve().parent
HERE=OFFICIAL.parent
PROJECT=HERE.parents[1]
METHODS=HERE.parent
sys.path.insert(0,str(HERE))
from qualification_pilot_rules import absolute_unit_evidence, cash_forward_relation, compare_adjustments, m1_p4_numeric_consistency, volume_amount_envelope

G1=METHODS/'_m2_smoke/g1_corporate_actions_20260909'
STATIC=METHODS/'_m2_codex_review/tonghuasun_static_20260909'
PLUGIN_SHA='19fbd89528ebe933cee267de34d63171afd47aef230132bd3574a3b81883469b'
START,END='2022-08-24','2026-09-04'
INDEX={'SH000300':('USZI399300','399300.SZ'), 'SH000001':('USHI1A0001','10001.SH')}
NUMBER_FIELDS={'open':'open','high':'high','low':'low','close':'latest','volume':'transaction_volume','amount':'transaction_amount'}
UNIT_REVIEW_SHA='7e2d12f3ff2ecf0d4c119608b811563f2832db9e69b6d3a82ee0ab5c48a973bd'
UNIT_STATIC_SHA='3256db3834097decbd5d8fb6fd90ec3cecca7f8ff1711f8a8b5483d01a56c88d'
UNIT_ANCHOR_SHA='fc812f6664a7eb3b2646e20454102cf13f27fc0769d21bfe6107191c1d777fda'
UNIT_PRECISION_REVIEW_SHA='30aceb70ba9c03808a568092cada11dff3e4c037e652a84e0e1b6f58cb44cfb5'
UNIT_PRECISION_VERIFICATION_SHA='d19579144a9089f7e9f6e94dc540f2c37ffddcd839bebc7d3de751cfd96bbaf6'
MANIFEST_SHA='97e251ae84fc927486127a96b4966ed8fc59fac0b744b7d6f186b2b1548886fe'


def digest(path):return sha256(Path(path).read_bytes()).hexdigest()
def canonical(value):return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
def read(path):
    def object_pairs(pairs):
        result={}
        for key,value in pairs:
            if key in result:raise ValueError('duplicate JSON key in evidence')
            result[key]=value
        return result
    def constant(value):raise ValueError('non-finite JSON constant in evidence')
    return json.loads(Path(path).read_bytes(),object_pairs_hook=object_pairs,parse_constant=constant)
def write(path,value):Path(path).write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')


def evidence(path,purpose):
    return {'path':str(Path(path).resolve()),'sha256':digest(path),'purpose':purpose}


def collector_identity(plan_kind,producer_pins):
    """Bind the actual entrypoint, while all dependency pins remain enforced."""
    names={'qualification':'capture.py','remaining_pilot_raw_quarantine':'collect_remaining.py','remaining_pilot_after_confirmed_login':'collect_remaining_after_login.py','remaining_pilot_residual_unissued':'collect_residual32.py','remaining_pilot_residual27':'collect_residual27.py','remaining_pilot_identity24':'collect_identity24.py'}
    if plan_kind not in names:raise ValueError('unrecognized capture plan kind')
    matches=[(path,pin) for path,pin in producer_pins.items() if Path(path).name==names[plan_kind]]
    if len(matches)!=1:raise ValueError('capture entrypoint pin missing or ambiguous')
    return matches[0]


def complete_scope_references(scope,artifacts):
    """A scope cannot borrow another symbol's body or omit its own preflight."""
    available={row['sha256'] for row in artifacts}
    required={scope[field] for field in ('raw_body_sha256','capture_receipt_sha256',
        'capture_producer_manifest_sha256','capture_preflight_sha256','collector_sha256')}
    if 'request_artifact_sha256' in scope:required.add(scope['request_artifact_sha256'])
    if not required<=available:raise ValueError('scope own evidence is missing')
    return sorted(available)


def unit_inputs():
    """Verify original pins and replay official/local observations independently."""
    report_path=HERE/'unit_semantics_static_review.md'
    static_path=HERE/'unit_semantics_static_verification.json'
    anchor_path=HERE/'unit_anchor_evidence.json'
    for path,pin in [(report_path,UNIT_REVIEW_SHA),(static_path,UNIT_STATIC_SHA),(anchor_path,UNIT_ANCHOR_SHA)]:
        if digest(path)!=pin:raise ValueError('reviewed unit evidence changed')
    static=read(static_path);anchor_document=read(anchor_path)
    files=[evidence(report_path,'reviewed stock quantity field and display semantics'),
        evidence(static_path,'independent extracted-resource verification'),
        evidence(anchor_path,'root-retained independent official absolute unit observations')]
    if digest(static['assembly'])!=static['assembly_sha256']:raise ValueError('unit resource assembly changed')
    files.append(evidence(static['assembly'],'fixed metadata assembly'))
    for name,pin in static['artifact_sha256'].items():
        path=HERE/name
        if digest(path)!=pin:raise ValueError('static unit evidence artifact changed')
        files.append(evidence(path,'source unit static evidence or retained inspection history'))
    if static['static_resource_verification_passed'] is not True:raise ValueError('static unit verification failed')
    if {(f['id'],f['english_name']) for f in static['fields']}!={(13,'Volume'),(19,'Turnover')}:
        raise ValueError('host fields do not match reviewed quantity semantics')
    for path,pin in anchor_document['input_pins'].items():
        if digest(path)!=pin:raise ValueError('absolute unit anchor input changed')
        files.append(evidence(path,'pinned original unit anchor input'))
    precision_path=HERE/'unit_semantics_static_precision_verification.json'
    precision_report=HERE/'unit_semantics_static_precision_review.md'
    if digest(precision_path)!=UNIT_PRECISION_VERIFICATION_SHA or digest(precision_report)!=UNIT_PRECISION_REVIEW_SHA:
        raise ValueError('reviewed auxiliary precision evidence changed')
    files.extend([evidence(precision_path,'auxiliary fixed-format resolution comparison; not an eligibility gate'),
                  evidence(precision_report,'local HxLong/Double format explanation; actual transport unknown')])
    for path,pin in read(precision_path)['input_pins'].items():
        if digest(path)!=pin:raise ValueError('auxiliary precision evidence input changed')
        files.append(evidence(path,'auxiliary source-format inspection, not a runtime-dtype assertion'))
    pins_by_hash={pin:Path(path) for path,pin in anchor_document['input_pins'].items()}
    def records(value):
        if isinstance(value,dict):
            if value.get('secCode')=='600011' and 'secTxVolume' in value:yield value
            for item in value.values():yield from records(item)
        elif isinstance(value,list):
            for item in value:yield from records(item)
    anchors=anchor_document['anchors']
    if {(a['symbol'],a['date']) for a in anchors}!={('SH600011','20221129'),('SH600011','20260529')}:
        raise ValueError('planned old/recent official anchors missing or changed')
    for anchor in anchors:
        if anchor['reference_sha256'] not in pins_by_hash or anchor['raw_sha256'] not in pins_by_hash:
            raise ValueError('anchor original bodies missing')
        reference_path=pins_by_hash[anchor['reference_sha256']]
        receipt=read(reference_path.with_name(reference_path.name+'.receipt.json'))
        if receipt['status']!=200 or receipt['sha256']!=anchor['reference_sha256'] or receipt['url']!=anchor['source_url']:
            raise ValueError('official unit response provenance mismatch')
        candidates={(r['secTxVolume'],r['secTxAmount'],r['abnormalStart'],r['abnormalEnd'],r['tradeDate'])
                    for r in records(read(reference_path))}
        if len(candidates)!=1:raise ValueError('official unit anchor is not unique')
        volume,amount,start,end,day=candidates.pop()
        if (start,end,day)!=(anchor['date'],)*3:raise ValueError('official unit reference is not that single day')
        security,rows=projection(pins_by_hash[anchor['raw_sha256']])
        if (security['hostFullCode'],security['fullCode'])!=('USHA600011','600011.SH'):
            raise ValueError('unit reference and local security differ')
        iso_day=day[:4]+'-'+day[4:6]+'-'+day[6:]
        local=[row for row in rows if row['date']==iso_day]
        if len(local)!=1:raise ValueError('local unit anchor date missing')
        for field,official in [('volume',volume),('amount',amount)]:
            recorded=anchor['comparisons'][field]
            if Decimal(recorded['official_decimal'])!=Decimal(official) or Decimal(recorded['ths_decimal'])!=Decimal(str(local[0][field])):
                raise ValueError('unit anchor recorded values do not replay from original bodies')
            if Decimal(recorded['difference_ths_minus_official'])!=Decimal(str(local[0][field]))-Decimal(official):
                raise ValueError('unit decimal difference not faithfully retained')
    # These assertions are the content of the pinned read-only IL review above.
    # XML alone is not claimed to establish the no-scaling/display call chain.
    semantics=dict(volume_field_id=13,amount_field_id=19,plugin_numeric_transform='identity',
        volume_display='raw_divided_by_share_count_per_unit',
        share_count_per_unit={m['id']:m['share_count_per_unit'] for m in static['markets']},
        amount_display='raw_with_magnitude_abbreviation_only')
    import xml.etree.ElementTree as ET
    resource=HERE/'unit_semantics_static_resource_Hevo.Core.DataModel.Data.MarketData.xml'
    if digest(resource)!='f8e251d1e74bef48d5d7ede03fc6e32e8ea288c218098515e0bf46b6bcffc2a6':raise ValueError('market resource changed')
    market=ET.fromstring(resource.read_bytes()).find("Market[@id='USHT']")
    if market is None or market.get('ShareCountPerUnit')!='100':raise ValueError('risk market unit not observed')
    semantics['share_count_per_unit']['USHT']=100
    identity=HERE/'identity_search_600289/response.bin'
    if digest(identity)!='5ad4d502d552933d4f20f54abfa1c7b17b01ea19790bc42a34a56ee80304b1d0':raise ValueError('risk identity evidence changed')
    files.extend([evidence(resource,'same stock quantity display contract for USHT; share count 100'),evidence(identity,'observed native risk-board identity for canonical SH600289')])
    return semantics,anchors,files


def cash_facts():
    facts=[]
    catalog=read(G1/'events.json')
    for event in catalog['events_in_interval']+catalog['events_excluded_by_date']:
        leg=event.get('legs',{}).get('implementation',event)
        document=G1/leg['artifact']
        facts.append(dict(symbol=event['issuer'],ex_date=leg['ex_dividend_date'],
            cash_per_share_CNY=str(leg['cash_per_share_before_tax']),
            document_path=str(document.resolve()),document_sha256=digest(document),
            url=leg['source_url'],page=leg['page_reference'],event_type='cash_implementation'))
    for year,day,cash,url in [
        ('2023','2023-07-05','0.068','https://static.cninfo.com.cn/finalpage/2023-06-26/1217139649.PDF'),
        ('2024','2024-06-05','0.11','https://static.cninfo.com.cn/finalpage/2024-05-29/1220197112.PDF')]:
        document=OFFICIAL/f'cninfo_832000_{year}_cash_implementation.pdf'
        facts.append(dict(symbol='BJ920000',ex_date=day,cash_per_share_CNY=cash,
            document_path=str(document.resolve()),document_sha256=digest(document),url=url,
            page='1 (gross cash per 10 shares); 2 (actual ex-date)',event_type='cash_implementation'))
    return sorted(facts,key=lambda row:(row['symbol'],row['ex_date']))


def identity_facts():
    mapping=G1/'official_notices/bse_code_mapping_new_old_codes.html'
    raw=mapping.read_text(encoding='utf-8-sig')
    target={'920000','920001','920006','920519','920627'}
    facts=[]
    for tr in re.findall(r'<tr\b[^>]*>(.*?)</tr>',raw,re.S|re.I):
        cells=[html.unescape(re.sub('<[^>]+>','',cell)).strip() for cell in re.findall(r'<td\b[^>]*>(.*?)</td>',tr,re.S|re.I)]
        if len(cells)==5 and cells[-1] in target:
            _,name,listed,old,new=cells
            y,m,d=map(int,listed.split('/'))
            facts.append(dict(symbol='BJ'+new,official_issuer_name=name,
                official_listing_date=f'{y:04}-{m:02}-{d:02}',old_code=old,
                identity_kind='exchange_old_new_code_mapping',effective_code_change_date=None,
                document_path=str(mapping.resolve()),document_sha256=digest(mapping),
                url='https://www.bse.cn/service/code_mapping.html',row_number=cells[0]))
    if len(facts)!=5:raise ValueError('official migration rows incomplete')
    listing_receipts={row['file']:row for row in read(OFFICIAL/'retrieval_listing_notices.json')}
    for code,name,listed in [('920002','万达轴承','2024-05-30'),('920003','中诚咨询','2025-11-07'),
                             ('920005','鼎佳精密','2025-07-31'),('920007','酉立智能','2025-08-08')]:
        document=OFFICIAL/f'cninfo_{code}_listing_notice.pdf'
        receipt=listing_receipts[document.name]
        if receipt['raw_sha256']!=digest(document):raise ValueError('listing document modified')
        facts.append(dict(symbol='BJ'+code,official_issuer_name=name,official_listing_date=listed,
            old_code=None,identity_kind='original_920_IPO',
            document_path=str(document.resolve()),document_sha256=digest(document),url=receipt['url'],
            page='1 (issuer, exchange listing date and new listed-security code)',
            note='No pre-IPO 8xxxxx stock code is required for the BSE eligible interval.'))
    return sorted(facts,key=lambda row:row['symbol'])


def projection(path):
    root=read(path)
    if root.get('ok') is not True or root.get('error') is not None:raise ValueError('source response not successful')
    items=root['data']['items']
    if len(items)!=1 or not items[0]['points']:raise ValueError('not exactly one nonempty source series')
    item=items[0];rows=[];seen=set()
    for point in item['points']:
        value=point['values'];day=str(value['date_time'])
        if not re.fullmatch('[0-9]{8}',day):raise ValueError('invalid date key')
        day=day[:4]+'-'+day[4:6]+'-'+day[6:]
        if day in seen:raise ValueError('duplicate day')
        seen.add(day)
        if value['full_code']!=item['security']['fullCode']:raise ValueError('mixed series identity')
        rows.append({'date':day,**{key:value[field] for key,field in NUMBER_FIELDS.items()}})
    return item['security'],rows


def compact_envelope(rows):
    result=volume_amount_envelope(rows)
    for value in result['scale_results'].values():
        value['first_violations']=value.pop('violations')[:5]
    return result


def build(capture_directories):
    cash=cash_facts();identities=identity_facts()
    write(OFFICIAL/'corporate_action_facts.json',cash)
    write(OFFICIAL/'identity_facts.json',identities)
    identity_by_symbol={fact['symbol']:fact for fact in identities}
    manifest=METHODS/'_m1_closure/pilot_symbols.csv'
    if digest(manifest)!=MANIFEST_SHA:raise ValueError('frozen pilot manifest changed')
    with manifest.open(encoding='utf-8-sig') as source:
        manifest_rows=list(csv.DictReader(source))
    entries={row['symbol']:row for row in manifest_rows}
    if len(manifest_rows)!=52 or len(entries)!=52 or {k for k,v in entries.items() if v['stratum']=='benchmark'}!=set(INDEX):
        raise ValueError('frozen population is not fifty stocks and two benchmarks')
    for symbol,fact in identity_by_symbol.items():
        if entries[symbol]['list_date']!=fact['official_listing_date']:raise ValueError('official and frozen listing dates disagree')
    unit_semantics,unit_anchors,unit_files=unit_inputs()

    source_files=[evidence(HERE/'qualification_pilot_rules.py','exact numerical evidence rules'),
        evidence(Path(__file__),'offline evidence assembly producer'),
        evidence(manifest,'frozen 50-stock plus two-benchmark universe'),
        evidence(HERE/'basis_constants_static.txt','read-only SDK enum constants and downstream protocol converter'),
        evidence(STATIC/'ths_il_evidence.txt','full reviewed adapter -> host path; no runtime target-DLL execution'),
        evidence(METHODS/'_m1_closure/acceptance_runner.py','unchanged formal P4 numeric gate low*0.98..high*1.02'),
        evidence(OFFICIAL/'sse_csi300_method.html','official 000300 Shanghai / 399300 Shenzhen index alias'),
        evidence(OFFICIAL/'sse_composite_method.pdf','official SSE Composite canonical index code 000001'),
        evidence(OFFICIAL/'NewIndexConfig.xml','installed host native index identifiers'),
        evidence(G1/'events.json','previously reviewed G1 factual index, not new corporate-action evidence'),
        evidence(OFFICIAL/'corporate_action_facts.json','official cash facts with original PDF hashes'),
        evidence(OFFICIAL/'identity_facts.json','five old/new mappings and four new BSE IPO identities')]
    source_files.extend(unit_files)
    for fact in cash+identities:
        row=evidence(fact['document_path'],'original official document')
        if row not in source_files:source_files.append(row)
    if digest(OFFICIAL/'NewIndexConfig.xml')!='daf3167c5d33acb41a325deee2b5c28232920bfd02c594b6d1e6cdb9b0207da1':
        raise ValueError('native mapping differs from reviewed static copy')
    static_text=(HERE/'basis_constants_static.txt').read_text(encoding='utf-8-sig')
    if 'FIELD Unadjusted = 0' not in static_text or 'FIELD Exclude = 0' not in static_text:
        raise ValueError('missing reviewed source constants')
    if digest(STATIC/'ths_il_evidence.txt')!='9d5b4c93210c1d2abb459531017130c9220f54ff93ccd67781f098a08d2135df':
        raise ValueError('frozen protocol chain differs')
    csi_text=(OFFICIAL/'sse_csi300_method.html').read_text(encoding='utf-8')
    if '000300' not in csi_text or '399300' not in csi_text:raise ValueError('index alias missing')
    fixed=HERE/'qualification_capture'
    for number in range(1,9):
        source_files.extend([
            evidence(fixed/f'response_{number}.bin','retained qualification control raw body'),
            evidence(fixed/f'completed_{number}.json','retained qualification control completion'),
            evidence(fixed/f'preflight_{number}.json','retained source plugin/process identity at capture')])
    controls={};diagnostics=[]
    for symbol,ids in [('SH600011',(3,4,5)),('BJ920000',(6,7,8))]:
        series={}
        for adjustment,number in enumerate(ids):
            _,rows=projection(fixed/f'response_{number}.bin')
            series[str(adjustment)]={row['date']:row for row in rows}
            diagnostics.append(dict(symbol=symbol,adjustment=adjustment,body_sha256=digest(fixed/f'response_{number}.bin'),
                envelope=compact_envelope(rows)))
        controls[symbol]=cash_forward_relation(series,[row for row in cash if row['symbol']==symbol])
    protocol_controls_pass=all(row['status']=='PASS' for row in controls.values())
    scopes=[];seen=set();rejected_attempts=[]
    for directory in capture_directories:
        plan_path=directory/'plan.json';plan=read(plan_path)
        producer_file=directory/'producer_pins.json';producer_pins=read(producer_file)
        collector=collector_identity(plan['kind'],producer_pins)
        for path,pin in producer_pins.items():
            if digest(path)!=pin:raise ValueError('captured producer changed')
            source_files.append(evidence(path,'exact entrypoint or dependency named in original producer manifest'))
        source_files.append(evidence(producer_file,'original capture producer pins'))
        source_files.append(evidence(plan_path,'original bounded collection plan'))
        for receipt_path in sorted(directory.glob('completed_*.json')):
            receipt=read(receipt_path);job=receipt['job'];payload=job['payload']
            if payload['adjustment']!=0:continue
            if receipt.get('stop_reason') is not None:
                rejected_attempts.append(dict(path=str(receipt_path),sha256=digest(receipt_path),reason=receipt['stop_reason']))
                continue
            symbol=job['symbol']
            if symbol not in entries:raise ValueError('unplanned security')
            if job not in plan['jobs']:raise ValueError('completion job absent from original plan')
            if symbol in seen:raise ValueError('multiple candidate bodies for one symbol')
            seen.add(symbol)
            body_path=directory/f"response_{job['id']}.bin";body_sha=digest(body_path)
            if receipt['raw_sha256']!=body_sha:raise ValueError('body changed after capture')
            preflight_path=directory/f"preflight_{job['id']}.json";preflight=read(preflight_path)
            if not preflight['passed'] or preflight['host_process']['adapter_sha256']!=PLUGIN_SHA:
                raise ValueError('source producer preflight mismatch')
            security,rows=projection(body_path)
            host_expected=(INDEX[symbol][0] if symbol in INDEX else
                {'SH':'USHA','SZ':'USZA','BJ':'USTM'}[symbol[:2]]+symbol[2:])
            if symbol=='SH600289':host_expected='USHT600289'
            full_expected=INDEX[symbol][1] if symbol in INDEX else symbol[2:]+'.'+symbol[:2]
            identity_ok=(security['hostFullCode']==host_expected and security['fullCode']==full_expected and
                payload['security']=={'hostFullCode':host_expected} and
                (not symbol.startswith('BJ') or symbol in identity_by_symbol))
            envelope=None if symbol in INDEX else compact_envelope(rows)
            p4=None if symbol in INDEX else m1_p4_numeric_consistency(rows)
            unit_policy=None if symbol in INDEX else absolute_unit_evidence(rows,security['hostMarketCode'],unit_semantics,unit_anchors)
            basis_ok=(protocol_controls_pass and identity_ok and payload['period']==7 and
                payload['startTimeUtc']=='2022-08-23T16:00:00Z' and payload['endTimeUtc']=='2026-09-04T15:59:59.999Z' and
                (symbol in INDEX or p4['status']=='PASS'))
            scope=dict(symbol=symbol,instrument_class='benchmark' if symbol in INDEX else 'stock',raw_body_sha256=body_sha,
                request_sha256=sha256(canonical(payload)).hexdigest(),capture_receipt_sha256=digest(receipt_path),
                capture_producer_manifest_sha256=digest(producer_file),collector_sha256=collector[1],
                capture_preflight_sha256=digest(preflight_path),collector_entrypoint=Path(collector[0]).name,
                start_date=START,end_date=END,period=7,adjustment=0,plugin_sha256=PLUGIN_SHA,
                rules_sha256=digest(HERE/'qualification_pilot_rules.py'),vendor_basis='unadjusted',
                vendor_basis_status='verified' if basis_ok else 'failed',
                unit_status='not_applicable' if symbol in INDEX else 'verified' if unit_policy['status']=='PASS' else 'failed',
                all_value_accuracy_verified=False,
                identity_status='verified' if identity_ok else 'failed',
                volume_unit='not_applicable' if symbol in INDEX else 'share',
                amount_unit='not_applicable' if symbol in INDEX else 'CNY',
                source_security=security,rows=len(rows),envelope=envelope,m1_p4_numeric_consistency=p4,unit_policy=unit_policy,
                interpretation='Source-unit evidence combines pinned field/display semantics, independently replayed official anchors and original P4. The bundle awaits independent review; no runtime dtype or exact decimal equality is claimed.')
            source_files.extend([evidence(body_path,'this scope exact raw observation'),
                evidence(receipt_path,'this scope exact capture receipt'),
                evidence(preflight_path,'this scope plugin/process identity at capture')])
            request_path=directory/f"request_{job['id']}.json"
            if request_path.exists():
                if read(request_path)!=payload or receipt.get('request_sha256')!=digest(request_path):
                    raise ValueError('retained request file differs from capture receipt')
                scope['request_artifact_sha256']=digest(request_path)
                source_files.append(evidence(request_path,'this scope exact request JSON artifact; separate from canonical payload hash'))
            scope['evidence_sha256']=complete_scope_references(scope,source_files)
            scopes.append(scope)
    audit_path=HERE/'audit_recovered_pilot_52.json'
    audited=read(audit_path)
    audit_by_symbol={row['symbol']:row for row in audited['scopes']}
    if len(audit_by_symbol)!=52 or audited['symbols']!=52:raise ValueError('full retained corpus audit missing')
    source_files.append(evidence(audit_path,'strict parser and unchanged listing-aware date coverage audit'))
    for scope in scopes:
        observed=audit_by_symbol[scope['symbol']]
        if observed.get('raw_sha256')!=scope['raw_body_sha256']:raise ValueError('audit and qualification body differ')
        scope['date_coverage_complete']=observed['status']=='complete_raw_key_inventory'
        scope['missing_dates']=observed['missing_dates']
        scope['identity_mapping_evidence_sha256']=('5ad4d502d552933d4f20f54abfa1c7b17b01ea19790bc42a34a56ee80304b1d0' if scope['symbol']=='SH600289' else None)
        scope['evidence_sha256']=sorted(set(scope['evidence_sha256'])|{digest(audit_path)})
    result=dict(schema='m2.ths.qualification_evidence.v1',evidence_mode='retained_market_capture',
        generated_at_utc=datetime.now(timezone.utc).isoformat(),rules_sha256=digest(HERE/'qualification_pilot_rules.py'),
        builder_sha256=digest(__file__),review_state='ready_for_independent_review',
        unit_evidence_policy=dict(anchor_sha256=UNIT_ANCHOR_SHA,static_review_sha256=UNIT_REVIEW_SHA,
            static_verification_sha256=UNIT_STATIC_SHA,precision_review_sha256=UNIT_PRECISION_REVIEW_SHA,
            precision_verification_sha256=UNIT_PRECISION_VERIFICATION_SHA,
            precision_comparison_is_auxiliary=True,new_anchor_requires_independent_review=True,
            all_value_accuracy_verified=False,
            rule='Pinned field/display semantics plus exactly reviewed official absolute anchors plus unchanged per-stock M1 P4. Fixed scale candidates reject common unit mistakes; they are not a general numerical accuracy threshold.'),
        basis_evidence_rule='Fixed implementation -> source protocol plus real 0/1/2 discrimination, independent official cash-event OHLC equality across full control windows, and every candidate stock frozen M1 P4 numeric gate. Additional exact amount/volume envelope is diagnostic only.',
        scope_limits=['No empirical adjustment parameter alone is sufficient.','Cash diagnostics alone grant no eligibility.',
            'Stock unit qualification does not use binary32 equality, HxLong half-grid comparison or any inferred transport dtype.',
            'Known unit-scale alternatives are rejected without fitting a new numerical-accuracy tolerance; decimal differences remain visible.',
            'Unit verification is bound to the exact reviewed anchor and static-evidence hashes. Replacing those observations requires fresh independent review, even when another candidate scale ranks first.',
            'Index amount and volume are not stock liquidity evidence.','No exact legal code-switch date is inferred from the old/new mapping.',
            'Official issuer names are identity references; corrupted raw source names are not replaced.',
            'Price/volume/amount adjustment consistency is verified for this pinned endpoint contract and retained corpus, not other vendor products.'],
        controls=controls,diagnostics=diagnostics,official_identity_facts=identities,
        official_cash_events=cash,scopes=scopes,artifacts=list({row['path']:row for row in source_files}.values()),
        rejected_capture_attempts=rejected_attempts,
        staging_eligible=(all(row['date_coverage_complete'] for row in scopes) and set(row['symbol'] for row in scopes)==set(entries) and
            all(row['vendor_basis_status']==row['identity_status']=='verified' and
                row['unit_status']==('not_applicable' if row['instrument_class']=='benchmark' else 'verified') for row in scopes)),
        all_value_accuracy_verified=False,live_trading=False,production_promotion=False)
    write(HERE/'qualification_pilot52.json',result)
    print(json.dumps({'scopes':len(scopes),'cash_controls':controls,'staging_eligible':result['staging_eligible']},ensure_ascii=True))


if __name__=='__main__':
    directories=[HERE/'qualification_capture']+[Path(value).resolve() for value in sys.argv[1:]]
    build(directories)
