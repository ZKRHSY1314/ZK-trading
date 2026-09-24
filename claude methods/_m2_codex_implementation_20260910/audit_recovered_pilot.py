"""Audit retained recovery partitions without fetching, filling or accepting data."""
from collections import Counter
from datetime import datetime, timezone
import csv
import importlib.util
import json
from pathlib import Path
import sys
import audit_pilot_raw as audit

HERE=Path(__file__).resolve().parent
audit.FIXED_PINS[audit.PARSER]='605d65965b1aee56f0f64c5c2446078aefa8d237d7a3d09b5f7403e4a24c2779'
_original_native_spec=audit.native_spec
def verified_native_spec(parser,symbol):
    if symbol=='SH600289':
        path=HERE/'identity_search_600289/response.bin'
        pin='5ad4d502d552933d4f20f54abfa1c7b17b01ea19790bc42a34a56ee80304b1d0'
        if audit.digest(path)!=pin:raise ValueError('risk board source identity evidence changed')
        return parser.SecuritySpec.stock(symbol,host_full_code='USHT600289',mapping_evidence=pin)
    return _original_native_spec(parser,symbol)
audit.native_spec=verified_native_spec
GROUPS={
    'qualification_capture':('capture.py', None),
    'remaining_capture_after_login':('collect_remaining_after_login.py', range(1,17)),
    'remaining_capture_residual32':('collect_residual32.py', range(17,22)),
    'remaining_capture_residual27':('collect_residual27.py', range(22,25)),
    'remaining_capture_identity24':('collect_identity24.py', range(25,49)),
}

def run():
    for path,pin in audit.FIXED_PINS.items():
        if audit.digest(path)!=pin:raise ValueError('fixed input changed')
    entries=list(csv.DictReader(audit.MANIFEST.open(encoding='utf-8-sig')))
    calendar=[audit.iso_day(day) for day in audit.read_json(audit.CALENDAR)]
    by_symbol={entry['symbol']:entry for entry in entries}
    if len(by_symbol)!=52:raise ValueError('expected 52 symbols')
    remaining=[entry['symbol'] for entry in entries if entry['symbol'] not in audit.REUSED]
    spec=importlib.util.spec_from_file_location('m2_recovered_parser',audit.PARSER)
    parser=importlib.util.module_from_spec(spec);sys.modules[spec.name]=parser;spec.loader.exec_module(parser)
    scopes=[];observations={};pins={};groups={}
    for group,(entrypoint,ids) in GROUPS.items():
        directory=HERE/group
        manifest=audit.read_json(directory/'producer_pins.json')
        if manifest.get(str((HERE/entrypoint).resolve()))!=audit.digest(HERE/entrypoint):
            raise ValueError('capture entrypoint mismatch')
        for name,pin in manifest.items():
            if audit.digest(name)!=pin:raise ValueError('capture producer changed')
            pins[name]=pin
        plan=audit.read_json(directory/'plan.json')
        summary=audit.read_json(directory/'summary.json')
        jobs=([audit.expected_job(parser,symbol,i) for symbol,i in audit.REUSED.items()]
            if ids is None else [audit.expected_job(parser,remaining[i-1],i) for i in ids])
        selected={job['id'] for job in jobs}
        actual=set(int(path.stem.split('_')[-1]) for path in directory.glob('completed_*.json'))
        if ids is None:actual-= {4,5,7,8}
        if group=='remaining_capture_residual27':
            rejected=audit.read_json(directory/'completed_25.json')
            body=directory/'response_25.bin'
            if rejected['stop_reason']!='empty_points' or rejected['raw_sha256']!=audit.digest(body):
                raise ValueError('failed identity attempt not retained')
            actual.discard(25)
        if actual!=selected:raise ValueError('selected partition has missing or extra receipts')
        for path in directory.iterdir():
            if path.is_file():pins[str(path)]=audit.digest(path)
        groups[group]={'entrypoint':entrypoint,'selected_jobs':sorted(selected),'summary':summary}
        for job in jobs:
            if job not in plan['jobs']:raise ValueError('job absent from captured plan')
            receipt=audit.read_json(directory/f"completed_{job['id']}.json")
            request=directory/f"request_{job['id']}.json"
            if ids is not None and (audit.read_json(request)!=job['payload'] or
                    audit.digest(request)!=receipt.get('request_sha256')):
                raise ValueError('exact request evidence mismatch')
            preflight=audit.read_json(directory/f"preflight_{job['id']}.json")
            if preflight.get('passed') is not True or preflight['endpoint_identity']['passed'] is not True:
                raise ValueError('capture preflight failed')
            symbol=job['symbol'];dates=audit.expected_dates(by_symbol[symbol],calendar)
            scope,observed=audit.audit_scope(parser,by_symbol[symbol],directory,job,dates,False)
            scopes.append(scope)
            if observed is not None:observations[symbol]=observed
    if len(scopes)!=52 or len({s['symbol'] for s in scopes})!=52:raise ValueError('partition not 52 distinct')
    expected=sum(s['expected_keys'] for s in scopes)
    if expected!=45935:raise ValueError('expected key contract changed')
    official_path=HERE/'unit_official/sse_abnormal_20260611.json'
    if audit.digest(official_path)!=audit.OFFICIAL_SHA:raise ValueError('official comparison input changed')
    comparisons=audit.compare_official(audit.official_records(audit.read_json(official_path)),observations,calendar)
    complete=all(s['status']=='complete_raw_key_inventory' for s in scopes)
    return dict(schema='m2.ths.recovered_pilot_audit.v1',at_utc=datetime.now(timezone.utc).isoformat(),
        source_groups=groups,scopes=scopes,symbols=len(scopes),expected_rows=expected,
        validated_rows=sum(s['validated_rows'] for s in scopes),
        observed_windows=dict(sum((Counter(s['candidate_windows']) for s in scopes),Counter())),
        missing_key_count=sum(len(s['missing_dates']) for s in scopes),
        extra_key_count=sum(len(s['extra_dates']) for s in scopes),
        statuses=dict(Counter(s['status'] for s in scopes)),raw_key_inventory_complete=complete,
        supplementary_official_comparisons=comparisons,input_pins=pins,
        failed_original_batch_preserved=str(HERE/'remaining_capture/summary.json'),
        producer_sha256=audit.digest(__file__),base_audit_sha256=audit.digest(audit.__file__),
        market_requests=0,database_opens=0,dataset_eligible=False,M2_complete=False)

if __name__=='__main__':
    destination=Path(sys.argv[1])
    result=run()
    with destination.open('x',encoding='utf-8') as handle:json.dump(result,handle,ensure_ascii=False,indent=2)
    print(json.dumps({k:result[k] for k in ('symbols','validated_rows','expected_rows','observed_windows',
        'missing_key_count','extra_key_count','statuses','raw_key_inventory_complete')},ensure_ascii=True))
    print(json.dumps({'gaps':[{'symbol':s['symbol'],'status':s['status'],'missing':s['missing_dates'],
        'extra':s['extra_dates'],'parser_error':s.get('parser_error')} for s in result['scopes']
        if s['status']!='complete_raw_key_inventory']},ensure_ascii=True))
    raise SystemExit(0 if result['raw_key_inventory_complete'] else 2)
