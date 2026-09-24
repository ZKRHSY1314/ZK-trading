"""Independent offline audit of the fixed M2 pilot's retained raw responses.

Only the pure history parser is imported by file path after its frozen hash is
checked. No transport, application initialization, database, repair, or eligibility
mutation occurs. --require-complete fails on incomplete/invalid raw key inventory;
the exclusive-create report is still retained. Official comparisons are diagnostic.
"""
from __future__ import annotations

import argparse
from collections import Counter
import csv
from datetime import date, datetime, timezone
from decimal import Decimal
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import re
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MANIFEST = ROOT/'claude methods/_m1_closure/pilot_symbols.csv'
CALENDAR = ROOT/'backend/.venv/Lib/site-packages/akshare/file_fold/calendar.json'
PARSER = ROOT/'backend/app/data/tonghuasun_history.py'
FIXED_PINS = {
    MANIFEST:'97e251ae84fc927486127a96b4966ed8fc59fac0b744b7d6f186b2b1548886fe',
    CALENDAR:'f1f1ce33c5cceb5c530c3271fc951405cb5624d2f30becec85dc7a85fd47e656',
    PARSER:'baacaa834e116e451a0d4e4ddafc681becf763c71d5e76232ea048bd72738437',
}
START, RESEARCH_START, END = '2022-08-24', '2023-09-04', '2026-09-04'
REUSED = {'SH000300':1, 'SH000001':2, 'SH600011':3, 'BJ920000':6}
OFFICIAL_TARGETS = {
    'SH600869':('2026-06-11','2026-06-11'),
    'SH600162':('2026-06-11','2026-06-11'),
    'SH600280':('2026-06-09','2026-06-11'),
}
OFFICIAL_SHA = '46ef7d0cddfb056c40cc992ce627c5a9afb951e44acf7c84b6c304ae28f9f95c'
OFFICIAL_JS_SHA = 'fed70791619c2a7d5a8b86e019eb86b046fb07e32233f9df5038fc21cd6d4d61'


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def iso_day(value):
    if not isinstance(value, str):
        raise ValueError('date_not_text')
    if re.fullmatch(r'\d{8}', value):
        value = f'{value[:4]}-{value[4:6]}-{value[6:]}'
    if not re.fullmatch(r'\d{4}-\d{2}-\d{2}', value):
        raise ValueError('date_format_invalid')
    return date.fromisoformat(value).isoformat()


def expected_dates(entry, calendar):
    """Listing eligibility changes the expected set, never the fixed window."""
    listing = None if entry['stratum']=='benchmark' else iso_day(entry['list_date'])
    delisting = iso_day(entry['delist_date']) if entry.get('delist_date') else None
    return [day for day in calendar if START<=day<=END
            and (listing is None or day>=listing) and (delisting is None or day<=delisting)]


def window_counts(days):
    return {'research':sum(RESEARCH_START<=d<=END for d in days),
            'warmup':sum(START<=d<RESEARCH_START for d in days)}


def native_spec(parser, symbol):
    if symbol=='SH000300':
        return parser.SecuritySpec.benchmark(symbol,host_full_code='USZI399300',response_full_code='399300.SZ',
            mapping_evidence='retained qualification_capture/completed_1.json; alias qualification is separate')
    if symbol=='SH000001':
        return parser.SecuritySpec.benchmark(symbol,host_full_code='USHI1A0001',response_full_code='10001.SH',
            mapping_evidence='retained qualification_capture/completed_2.json; formatter and canonical alias are separate')
    return parser.SecuritySpec.stock(symbol)


def expected_job(parser, symbol, job_id):
    spec = native_spec(parser,symbol)
    return {'id':job_id,'symbol':symbol,'host_full_code':spec.host_full_code,
        'payload':{'market':1,'security':{'hostFullCode':spec.host_full_code},
            'startTimeUtc':'2022-08-23T16:00:00Z','endTimeUtc':'2026-09-04T15:59:59.999Z',
            'limit':5000,'fields':list(parser.FIELDS),'period':7,'adjustment':0}}


def retained_request_evidence(directory, job, receipt):
    """The qualification producer embeds request payload in its attempt receipt.

    The remaining producer additionally retains standalone request bytes. Require
    exactly the artifacts its pinned implementation writes, without inventing a
    new requirement that the old qualification capture never promised.
    """
    attempt_path=directory/f"attempt_{job['id']}.json"
    attempt=read_json(attempt_path)
    if (attempt.get('job')!=job or attempt.get('state')!='reserved_before_http'
            or attempt.get('reserved_at')!=receipt.get('reserved_at')):
        raise ValueError('attempt_request_contract_mismatch')
    result={'request_evidence_path':str(attempt_path),'attempt_sha256':digest(attempt_path),
        'request_payload_canonical_sha256':hashlib.sha256(json.dumps(job['payload'],sort_keys=True,
            separators=(',',':'),allow_nan=False).encode()).hexdigest()}
    if directory.name=='remaining_capture':
        path=directory/f"request_{job['id']}.json"
        if read_json(path)!=job['payload'] or digest(path)!=receipt.get('request_sha256'):
            raise ValueError('retained_request_contract_mismatch')
        result.update(request_evidence_path=str(path),request_sha256=digest(path))
    return result


def official_records(body):
    """Only exchange security totals; never sum top broker buy/sell branches."""
    result = {symbol:set() for symbol in OFFICIAL_TARGETS}
    def visit(value):
        if isinstance(value,dict):
            symbol = 'SH'+str(value.get('secCode',''))
            if symbol in result and 'secTxVolume' in value and 'secTxAmount' in value:
                result[symbol].add((iso_day(value['abnormalStart']),iso_day(value['abnormalEnd']),
                    iso_day(value['tradeDate']),str(value['secTxVolume']),str(value['secTxAmount'])))
            for child in value.values():
                visit(child)
        elif isinstance(value,list):
            for child in value:
                visit(child)
    visit(body)
    return result


def compare_official(records, observed_by_symbol, calendar):
    """No partial-period comparison: all interval dates must have validated raw rows."""
    result = []
    for symbol,(start,end) in OFFICIAL_TARGETS.items():
        wanted = [day for day in calendar if start<=day<=end]
        item = {'symbol':symbol,'official_interval_start':start,'official_interval_end':end,
            'expected_comparison_dates':wanted,'diagnostic_only':True,'source_qualified':False}
        candidates = records.get(symbol,set())
        if len(candidates)!=1:
            item.update(status='official_summary_missing_or_ambiguous',comparison=None)
        else:
            actual_start,actual_end,report_day,volume,amount = next(iter(candidates))
            if (actual_start,actual_end,report_day)!=(start,end,end) or not wanted:
                item.update(status='official_interval_contract_mismatch',comparison=None)
            else:
                item.update(official_volume_decimal=volume,official_amount_decimal=amount,
                    official_volume_unit='share',official_amount_unit='CNY',
                    official_scope='exchange auction trade totals; block and after-hours fixed-price trades excluded')
                observed = observed_by_symbol.get(symbol)
                if observed is None:
                    item.update(status='no_validated_raw_scope',missing_dates=wanted,comparison=None)
                else:
                    missing = sorted(set(wanted)-set(observed))
                    if missing:
                        item.update(status='missing_observed_dates',missing_dates=missing,comparison=None)
                    else:
                        points = [observed[day] for day in wanted]
                        comparisons = {}
                        for field,reference in [('volume',volume),('amount',amount)]:
                            left = Decimal(reference)
                            values = [Decimal(point[field]) for point in points]
                            if not left.is_finite() or not all(x.is_finite() for x in values):
                                raise ValueError('official_comparison_nonfinite')
                            total = sum(values,Decimal(0))
                            comparisons[field] = {'official_decimal':str(left),'ths_period_sum_decimal':str(total),
                                'difference_ths_minus_official':str(total-left),'exact_decimal_equal':total==left,
                                'relative_difference':str((total-left)/left) if left else None}
                        item.update(status='compared_same_interval',comparison=comparisons,
                            observed_dates=wanted,observations=[dict(date=day,**observed[day]) for day in wanted],
                            no_partial_period_sum=True,eligibility_granted=False)
        result.append(item)
    return result


def audit_scope(parser, entry, directory, job, dates, pin_error):
    symbol = entry['symbol']
    receipt_path = directory/f"completed_{job['id']}.json"
    raw_path = directory/f"response_{job['id']}.bin"
    out = {'symbol':symbol,'stratum':entry['stratum'],'listing_date':entry.get('list_date') or None,
        'capture_directory':directory.name,'job_id':job['id'],'requested_adjustment':'none',
        'expected_keys':len(dates),'expected_windows':window_counts(dates),
        'status':'missing_capture_receipt','raw_row_count':None,'business_keys':[],
        'validated_rows':0,'candidate_windows':{'research':0,'warmup':0},
        'scope_rejected_raw_rows':0,'row_rejections':[],'missing_dates':dates,'extra_dates':[],
        'name_diagnostic_counts':{},'name_diagnostics':[],'name_diagnostics_evaluated':False,
        'eligible':False,'source_qualified':False}
    if not receipt_path.is_file():
        out['raw_exists_without_completed_receipt'] = raw_path.is_file()
        return out,None
    try:
        receipt = read_json(receipt_path)
        out.update(receipt_sha256=digest(receipt_path),observed_at=receipt.get('observed_at'))
        if not raw_path.is_file():
            out['status']='missing_raw_body'
            return out,None
        raw = raw_path.read_bytes()
        out.update(raw_sha256=hashlib.sha256(raw).hexdigest(),raw_bytes=len(raw))
        try:
            envelope = json.loads(raw)
            points = envelope['data']['items'][0]['points']
            out['raw_row_count'] = len(points) if isinstance(points,list) else None
        except (ValueError,TypeError,KeyError,IndexError):
            out['raw_row_count'] = None
        errors = []
        if pin_error:
            errors.append('producer_or_plan_pin_error')
        if receipt.get('job') != job:
            errors.append('receipt_job_contract_mismatch')
        if receipt.get('raw_sha256')!=out['raw_sha256'] or receipt.get('raw_bytes')!=len(raw):
            errors.append('receipt_raw_pin_mismatch')
        if receipt.get('http_status')!=200 or receipt.get('stop_reason') is not None or receipt.get('state')!='received_unqualified':
            errors.append('capture_not_successfully_completed')
        if receipt.get('row_count')!=out['raw_row_count']:
            errors.append('receipt_row_count_mismatch')
        observed = datetime.fromisoformat(receipt.get('observed_at','').replace('Z','+00:00'))
        if observed.utcoffset() is None:
            errors.append('receipt_observed_at_timezone_missing')
        try:
            out.update(retained_request_evidence(directory,job,receipt))
        except (OSError,ValueError,KeyError,TypeError):
            errors.append('retained_request_contract_mismatch')
        if errors:
            out.update(status='capture_evidence_rejected',capture_errors=errors,
                scope_rejected_raw_rows=out['raw_row_count'])
            return out,None
        try:
            parsed = parser.parse_history_response(raw,native_spec(parser,symbol),START,END,
                adjustment='none',expected_dates=dates)
        except parser.HistoryValidationError as exc:
            out.update(status='parser_rejected',parser_error={'code':exc.code,'row_index':exc.row_index},
                scope_rejected_raw_rows=out['raw_row_count'],invalid_row_count=None,
                invalid_count_note='pure parser fails at the first invalid observation; count is not inferred')
            return out,None
        if receipt.get('source_security')!=parsed['response_identity']:
            out.update(status='capture_evidence_rejected',capture_errors=['receipt_source_identity_mismatch'],
                scope_rejected_raw_rows=out['raw_row_count'])
            return out,None
        if parsed['eligible'] or parsed['mapping_verified'] or any(parsed[k]!='unverified' for k in ('volume_unit','amount_unit','vendor_basis')):
            raise ValueError('pure_parser_qualification_boundary_changed')
        rows = parsed['rows']
        wanted = set(dates)
        accepted_dates = [r['date'] for r in rows if r['date'] in wanted]
        extra = parsed['coverage']['extra_dates']
        nontrading_or_listing = [dict(date=r['date'],point_index=r['point_index'],reason='outside_listing_aware_calendar')
            for r in rows if r['date'] not in wanted]
        out.update(status='complete_raw_key_inventory' if parsed['coverage']['complete'] else 'incomplete_raw_key_inventory',
            source_identity=parsed['response_identity'],validated_rows=len(rows),invalid_row_count=0,
            business_keys=[[symbol,r['date'],'none',r['point_index']] for r in rows],
            candidate_windows=window_counts(accepted_dates),scope_rejected_raw_rows=0,
            row_rejections=nontrading_or_listing,row_rejected_windows=window_counts(extra),
            missing_dates=parsed['coverage']['missing_dates'],extra_dates=extra,
            first_date=parsed['first_date'],last_date=parsed['last_date'],
            name_diagnostic_counts=dict(Counter(d['code'] for d in parsed['name_diagnostics'])),
            name_diagnostics=parsed['name_diagnostics'],name_diagnostics_evaluated=True,item_name_status=parsed['item_name_status'],
            item_source_name=parsed['item_source_name'])
        # Exact source decimal values from retained JSON, indexed through the pure
        # parser's validated point_index. Never sum binary float parser outputs.
        exact = json.loads(raw,parse_float=Decimal,parse_int=Decimal)['data']['items'][0]['points']
        decimals = {r['date']:{'point_index':r['point_index'],'raw_sha256':out['raw_sha256'],
            'volume':str(exact[r['point_index']]['values']['transaction_volume']),
            'amount':str(exact[r['point_index']]['values']['transaction_amount'])}
            for r in rows if r['date'] in wanted}
        return out,decimals
    except (OSError,ValueError,TypeError,KeyError,AttributeError) as exc:
        out.update(status='capture_evidence_rejected',capture_errors=['malformed_retained_evidence'],
            error_type=type(exc).__name__,scope_rejected_raw_rows=out['raw_row_count'])
        return out,None


def audit():
    hashes = {str(path):digest(path) for path in FIXED_PINS}
    if any(hashes[str(path)]!=pin for path,pin in FIXED_PINS.items()):
        raise ValueError('frozen_manifest_calendar_or_parser_pin_changed')
    entries = list(csv.DictReader(io.StringIO(MANIFEST.read_text(encoding='utf-8-sig'))))
    if len(entries)!=52 or len({e['symbol'] for e in entries})!=52:
        raise ValueError('frozen_population_invalid')
    days = [iso_day(x) for x in read_json(CALENDAR)]
    if days!=sorted(set(days)):
        raise ValueError('calendar_duplicate_or_unordered')
    keys = {e['symbol']:expected_dates(e,days) for e in entries}
    totals = Counter()
    for dates in keys.values():
        totals.update(window_counts(dates))
    if sum(map(len,keys.values()))!=45935 or dict(totals)!={'research':36193,'warmup':9742}:
        raise ValueError('frozen_expected_business_key_counts_changed')
    spec = importlib.util.spec_from_file_location('m2_independent_raw_audit_parser',PARSER)
    parser = importlib.util.module_from_spec(spec)
    sys.modules[spec.name]=parser
    spec.loader.exec_module(parser)
    remaining = [e['symbol'] for e in entries if e['symbol'] not in REUSED]
    groups = {'qualification_capture':[expected_job(parser,symbol,i) for symbol,i in REUSED.items()],
        'remaining_capture':[expected_job(parser,symbol,i) for i,symbol in enumerate(remaining,1)]}
    pin_checks,group_errors,inventory,extra_receipts,extra_files,actual_symbols = {},{},[],[],[],set()
    for group,jobs in groups.items():
        directory = HERE/group
        errors = []
        if directory.is_dir():
            allowed_producers = ({HERE/'capture.py',HERE/'preflight.ps1',HERE/'test_capture.py',
                HERE/'qualification_plan.json',ROOT/'claude methods/_m2_codex_review/tonghuasun_static_20260909/endpoint_identity_guard.py'}
                if group=='qualification_capture' else {HERE/'collect_remaining.py',HERE/'test_collect_remaining.py',
                HERE/'capture.py',HERE/'preflight.ps1',HERE/'preflight_remaining.ps1',MANIFEST,CALENDAR,
                HERE/'qualification_capture/producer_pins.json',HERE/'qualification_capture/summary.json'})
            try:
                pins = read_json(directory/'producer_pins.json')
                if {Path(p) for p in pins}!=allowed_producers:
                    errors.append('producer_inventory_mismatch')
                for filename,expected in pins.items():
                    path = Path(filename)
                    if path not in allowed_producers:
                        continue
                    actual = digest(path)
                    hashes[str(path)]=actual
                    pin_checks[f'{group}:{filename}']={'expected':expected,'actual':actual,'match':actual==expected}
                    if actual!=expected:
                        errors.append('producer_pin_mismatch')
                plan = read_json(directory/'plan.json')
                byid = {j['id']:j for j in plan['jobs']}
                if len(byid)!=len(plan['jobs']) or any(byid.get(j['id'])!=j for j in jobs):
                    errors.append('capture_plan_jobs_mismatch')
                if group=='remaining_capture' and (plan['jobs']!=jobs or plan.get('reused_qualification_jobs')!=REUSED):
                    errors.append('remaining_plan_population_mismatch')
                if group=='remaining_capture' and plan.get('operator_policy')!='fixed_completed_history_any_time':
                    errors.append('remaining_plan_operator_policy_mismatch')
            except (OSError,ValueError,KeyError,TypeError):
                errors.append('capture_plan_or_pins_unreadable')
            for path in sorted(directory.iterdir()):
                if not path.is_file() or not (re.fullmatch(r'(response_\d+\.bin|completed_\d+\.json|request_\d+\.json|attempt_\d+\.json)',path.name)
                        or path.name in ('plan.json','producer_pins.json','summary.json')):
                    continue
                sha = digest(path)
                hashes[str(path)]=sha
                inventory.append({'path':str(path),'sha256':sha,'bytes':path.stat().st_size})
                numbered=re.fullmatch(r'(?:response|completed|request|attempt)_(\d+)\.(?:bin|json)',path.name)
                allowed_ids=set(range(1,9)) if group=='qualification_capture' else {j['id'] for j in jobs}
                if numbered and int(numbered.group(1)) not in allowed_ids:
                    extra_files.append(str(path))
                match = re.fullmatch(r'completed_(\d+)\.json',path.name)
                if match:
                    job_id = int(match.group(1))
                    if group=='qualification_capture' and job_id in (4,5,7,8):
                        continue
                    try:
                        receipt = read_json(path)
                        symbol = receipt['job']['symbol']
                        if isinstance(symbol,str):
                            actual_symbols.add(symbol)
                        if job_id not in {j['id'] for j in jobs}:
                            extra_receipts.append(str(path))
                    except (OSError,ValueError,TypeError,KeyError):
                        errors.append('completed_receipt_inventory_unreadable')
        group_errors[group]=sorted(set(errors))
    scopes,observed_by_symbol = [],{}
    by_symbol = {e['symbol']:e for e in entries}
    for group,jobs in groups.items():
        for job in jobs:
            symbol=job['symbol']
            scope,observed=audit_scope(parser,by_symbol[symbol],HERE/group,job,keys[symbol],group_errors[group])
            scopes.append(scope)
            if observed is not None:
                observed_by_symbol[symbol]=observed
    official_path = HERE/'unit_official/sse_abnormal_20260611.json'
    official_receipt = official_path.with_name(official_path.name+'.receipt.json')
    official_js = HERE/'unit_official/sse_public_query.js'
    try:
        receipt=read_json(official_receipt)
        for path in [official_path,official_receipt,official_js]:
            hashes[str(path)]=digest(path)
        if (digest(official_path)!=OFFICIAL_SHA or receipt.get('sha256')!=OFFICIAL_SHA or receipt.get('status')!=200
                or receipt.get('url')!='https://query.sse.com.cn/marketdata/tradedata/queryAllTradeOpenDate.do?token=QUERY&tradeDate=20260611&flag=1'
                or digest(official_js)!=OFFICIAL_JS_SHA):
            raise ValueError('official_input_pin_or_origin_mismatch')
        official=compare_official(official_records(read_json(official_path)),observed_by_symbol,days)
    except (OSError,ValueError,KeyError,TypeError):
        official=[{'status':'official_evidence_missing_or_rejected','diagnostic_only':True,'comparison':None}]
    expected_symbols=set(keys)
    complete = (actual_symbols==expected_symbols and not extra_receipts and not extra_files and not any(group_errors.values())
        and all(s['status']=='complete_raw_key_inventory' for s in scopes))
    hashes[str(Path(__file__))]=digest(Path(__file__))
    return {'schema':'m2.independent_pilot_raw_audit.v1','created_at':datetime.now(timezone.utc).isoformat(),
        'window':{'start':START,'research_start':RESEARCH_START,'end':END},
        'business_key_columns':['canonical_symbol','trade_date','requested_adjustment','original_point_index'],
        'expected_symbol_count':52,'expected_symbols':sorted(expected_symbols),'actual_symbol_count':len(actual_symbols),
        'actual_symbols':sorted(actual_symbols),'missing_symbols':sorted(expected_symbols-actual_symbols),
        'extra_symbols':sorted(actual_symbols-expected_symbols),'extra_completed_receipts':extra_receipts,
        'unexpected_capture_files':extra_files,
        'actual_symbol_definition':'symbols declared by selected completed receipts; verified scopes are reported separately',
        'verified_symbol_count':sum(s['validated_rows']>0 for s in scopes),
        'expected_business_keys':45935,'expected_window_rows':dict(totals),
        'validated_raw_rows':sum(s['validated_rows'] for s in scopes),
        'candidate_window_rows':{name:sum(s['candidate_windows'][name] for s in scopes) for name in ('research','warmup')},
        'rejected_scopes':[s['symbol'] for s in scopes if s['status'] in ('capture_evidence_rejected','parser_rejected')],
        'known_scope_rejected_raw_rows':sum(s['scope_rejected_raw_rows'] or 0 for s in scopes),
        'rejected_raw_rows_with_unknown_count_scopes':[s['symbol'] for s in scopes if s['scope_rejected_raw_rows'] is None],
        'listing_or_calendar_rejected_row_count':sum(len(s['row_rejections']) for s in scopes),
        'missing_key_count':sum(len(s['missing_dates']) for s in scopes),
        'extra_key_count':sum(len(s['extra_dates']) for s in scopes),
        'name_diagnostic_counts':dict(sum((Counter(s['name_diagnostic_counts']) for s in scopes),Counter())),
        'scope_status_counts':dict(Counter(s['status'] for s in scopes)),
        'raw_key_inventory_complete':complete,'scopes':scopes,
        'capture_group_errors':group_errors,'producer_pin_checks':pin_checks,'retained_file_inventory':inventory,
        'files_sha256':hashes,'supplementary_official_comparisons':official,
        'excluded_from_pilot':'qualification jobs 4/5/7/8 are adjustment probes; their files are inventoried but their rows are not duplicated',
        'requests_issued':0,'database_opens':0,'source_qualified':False,'dataset_eligible':False,'M2_complete':False,
        'completion_semantics':'--require-complete covers retained raw identities/requests/listing-aware keys; names and official comparisons remain diagnostics, not eligibility grants'}


def main():
    args=argparse.ArgumentParser(description=__doc__)
    args.add_argument('--out',type=Path,default=HERE/'audit_pilot_raw_report.json')
    args.add_argument('--require-complete',action='store_true')
    opts=args.parse_args()
    # Reserve exclusively before reading; no existing audit can be overwritten.
    with opts.out.open('x',encoding='utf-8',newline='\n') as handle:
        try:
            report=audit()
        except (OSError,ValueError,TypeError,KeyError) as exc:
            report={'schema':'m2.independent_pilot_raw_audit.v1','raw_key_inventory_complete':False,
                'fatal_error':str(exc),'requests_issued':0,'database_opens':0,'dataset_eligible':False}
        json.dump(report,handle,ensure_ascii=False,indent=2)
        handle.write('\n')
    print(json.dumps({'out':str(opts.out),'sha256':digest(opts.out),
        'actual_symbols':report.get('actual_symbol_count'),'validated_raw_rows':report.get('validated_raw_rows'),
        'raw_key_inventory_complete':report['raw_key_inventory_complete'],'dataset_eligible':False},ensure_ascii=False))
    return 2 if report.get('fatal_error') or (opts.require_complete and not report['raw_key_inventory_complete']) else 0


if __name__=='__main__':
    raise SystemExit(main())
