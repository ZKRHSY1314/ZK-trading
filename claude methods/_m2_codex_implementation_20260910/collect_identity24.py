"""Collect the other 48 frozen pilot stocks into raw quarantine, no databases.

Uses the reviewed market-only transport and preflight from the completed eight
request qualification run. Source qualification and research acceptance remain
separate. Existing four instruments are reused with their original provenance.
"""
from __future__ import annotations
import argparse
import csv
from datetime import datetime,timezone
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import time
import http.client
import base64

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
MANIFEST=ROOT/'claude methods/_m1_closure/pilot_symbols.csv'
MANIFEST_PIN='97e251ae84fc927486127a96b4966ed8fc59fac0b744b7d6f186b2b1548886fe'
CALENDAR=ROOT/'backend/.venv/Lib/site-packages/akshare/file_fold/calendar.json'
CALENDAR_PIN='f1f1ce33c5cceb5c530c3271fc951405cb5624d2f30becec85dc7a85fd47e656'
REMAINING_PREFLIGHT_PIN='26cc84463cffe7909adc3a93a39c3b523053359ecab7efd22b1ee541ad02d63a'
spec=importlib.util.spec_from_file_location('reviewed_m2_capture',HERE/'capture.py')
base=importlib.util.module_from_spec(spec);spec.loader.exec_module(base)

def preflight():
    """Same identity guard as the retained run; fixed past-history operator policy."""
    guard_path=base.PRIOR/'endpoint_identity_guard.py'
    if base.sha(guard_path.read_bytes())!='db6c3b6d4dc385cc39a05ad6a8d5cc1d0019d2a2b5988e0af22eea1a637b6483':
        raise base.StopCapture('identity_guard_pin_mismatch')
    spec=importlib.util.spec_from_file_location('m2_remaining_endpoint_guard',guard_path)
    guard=importlib.util.module_from_spec(spec);spec.loader.exec_module(guard)
    script=HERE/'preflight_residual27.ps1'
    if base.sha(script.read_bytes())!=REMAINING_PREFLIGHT_PIN:
        raise base.StopCapture('remaining_preflight_pin_mismatch')
    encoded=base64.b64encode(script.read_text(encoding='utf-8-sig').encode('utf-16le')).decode('ascii')
    observed=subprocess.run([str(base.PW),'-NoProfile','-NonInteractive','-EncodedCommand',encoded],
        capture_output=True,timeout=30,encoding='utf-8-sig')
    if observed.returncode:raise base.StopCapture('runtime_inventory_failed')
    try:
        metadata=json.loads(observed.stdout)
        endpoint_path=base.HOME/'runtime/endpoint.json'
        endpoint_raw=endpoint_path.read_bytes();endpoint=json.loads(endpoint_raw)
        host=metadata['host_process']
        identity=guard.validate_endpoint_identity(endpoint,current_pid=host['pid'],
            host_created_at=host['started_utc'],
            endpoint_mtime=datetime.fromtimestamp(endpoint_path.stat().st_mtime,timezone.utc))
        if metadata.get('passed') is not True or identity['passed'] is not True:
            base.write_json(HERE/('residual_preflight_failure_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%f')+'.json'),{'metadata':metadata,'endpoint_identity':identity}); raise base.StopCapture('runtime_identity_not_ready')
        metadata['endpoint_identity']=identity;metadata['endpoint_sha256']=base.sha(endpoint_raw)
        metadata['operator_policy']='fixed_completed_history_any_time'
        return metadata
    except (ValueError,TypeError,KeyError,OSError):
        raise base.StopCapture('runtime_metadata_unusable') from None

def pinned_inputs():
    sealed=json.loads((HERE/'qualification_capture/producer_pins.json').read_bytes())
    for raw_path,pin in sealed.items():
        if base.sha(Path(raw_path).read_bytes())!=pin:
            raise base.StopCapture('qualification_producer_changed')
    for path,pin in [(MANIFEST,MANIFEST_PIN),(CALENDAR,CALENDAR_PIN)]:
        if base.sha(path.read_bytes())!=pin:raise base.StopCapture('frozen_contract_changed')
    if base.sha((HERE/'preflight_residual27.ps1').read_bytes())!=REMAINING_PREFLIGHT_PIN:
        raise base.StopCapture('remaining_preflight_pin_mismatch')
    summary=json.loads((HERE/'qualification_capture/summary.json').read_bytes())
    if summary['attempts']!=8 or summary['stop_reason'] is not None:
        raise base.StopCapture('qualification_capture_incomplete')
    for i in [1,2,3,6]:
        receipt=json.loads((HERE/f'qualification_capture/completed_{i}.json').read_bytes())
        if base.sha((HERE/f'qualification_capture/response_{i}.bin').read_bytes())!=receipt['raw_sha256']:
            raise base.StopCapture('retained_raw_changed')
    return sealed

def plan():
    pinned_inputs()
    entries=list(csv.DictReader(io.StringIO(MANIFEST.read_text(encoding='utf-8-sig'))))
    if len(entries)!=52 or len({r['symbol'] for r in entries})!=52:
        raise base.StopCapture('frozen_population_invalid')
    reused={'SH000300':1,'SH000001':2,'SH600011':3,'BJ920000':6}
    jobs=[]
    for entry in entries:
        symbol=entry['symbol']
        if symbol in reused:continue
        if entry['stratum']=='benchmark':raise base.StopCapture('unexpected_benchmark')
        host={'SH':'USHA','SZ':'USZA','BJ':'USTM'}[symbol[:2]]+symbol[2:]
        jobs.append({'id':len(jobs)+1,'symbol':symbol,'host_full_code':host,
            'payload':{'market':1,'security':{'hostFullCode':host},
            'startTimeUtc':'2022-08-23T16:00:00Z','endTimeUtc':'2026-09-04T15:59:59.999Z',
            'limit':5000,'fields':['full_code','security_name','open','high','low','latest',
            'transaction_volume','transaction_amount','date_time'],'period':7,'adjustment':0}})
    if len(jobs)!=48:raise base.StopCapture('remaining_population_mismatch')
    previous=HERE/'remaining_capture_after_login'
    prior_summary=json.loads((previous/'summary.json').read_bytes())
    if prior_summary['attempts']!=16 or prior_summary['unissued']!=32 or prior_summary['stop_reason']!='runtime_identity_not_ready':
        raise base.StopCapture('prior_batch_not_fixed_residual32_state')
    for previous_job in jobs[:16]:
        receipt=json.loads((previous/f"completed_{previous_job['id']}.json").read_bytes())
        if receipt['job']!=previous_job or receipt.get('stop_reason') is not None or receipt.get('http_status')!=200 or base.sha((previous/f"response_{previous_job['id']}.bin").read_bytes())!=receipt['raw_sha256']:
            raise base.StopCapture('previous_success_not_reusable')
    residual=HERE/'remaining_capture_residual32'
    residual_summary=json.loads((residual/'summary.json').read_bytes())
    if residual_summary['attempts']!=5 or residual_summary['unissued']!=27 or residual_summary['stop_reason']!='runtime_identity_not_ready':
        raise base.StopCapture('prior_batch_not_fixed_residual27_state')
    for previous_job in jobs[16:21]:
        receipt=json.loads((residual/f"completed_{previous_job['id']}.json").read_bytes())
        if receipt['job']!=previous_job or receipt.get('stop_reason') is not None or receipt.get('http_status')!=200 or base.sha((residual/f"response_{previous_job['id']}.bin").read_bytes())!=receipt['raw_sha256']:
            raise base.StopCapture('previous_residual_success_not_reusable')
    searched=json.loads((HERE/'identity_search_remaining23/summary.json').read_bytes())['identities']
    risk=json.loads((HERE/'identity_search_600289/response.bin').read_bytes())['data']['items']
    if len(searched)!=23 or len(risk)!=1 or risk[0]['hostFullCode']!='USHT600289' or risk[0]['fullCode']!='600289.SH':
        raise base.StopCapture('identity_evidence_invalid')
    for item in searched:
        job=jobs[item['job_id']-1]
        raw=HERE/f"identity_search_remaining23/response_{item['job_id']}.bin"
        if base.sha(raw.read_bytes())!=item['raw_sha256'] or item['symbol']!=job['symbol'] or item['security']['hostFullCode']!=job['host_full_code']:
            raise base.StopCapture('remaining_native_identity_changed')
    prior=HERE/'remaining_capture_residual27'
    state=json.loads((prior/'summary.json').read_bytes())
    if state['attempts']!=4 or state['unissued']!=23 or state['stop_reason']!='empty_points':
        raise base.StopCapture('prior_state_not_fixed_identity_recovery')
    for job in jobs[21:24]:
        receipt=json.loads((prior/f"completed_{job['id']}.json").read_bytes())
        if receipt['job']!=job or receipt.get('stop_reason') is not None or base.sha((prior/f"response_{job['id']}.bin").read_bytes())!=receipt['raw_sha256']:
            raise base.StopCapture('previous_success_changed')
    jobs[24]['host_full_code']='USHT600289'
    jobs[24]['payload']['security']={'hostFullCode':'USHT600289'}
    return {'kind':'remaining_pilot_identity24','prior_failed_raw_sha256':'78fd5a3a4bb03c0e3bc243b2f9fb0f9e967ca427bdacedf679e7cf033e6850e9','max_attempts':24,'jobs':jobs[24:],
        'reused_qualification_jobs':reused,'authorization':'User explicitly asked Codex to continue until M2 completion.',
        'min_seconds_after_completion':base.INTERVAL,'absolute_request_timeout':base.TIMEOUT,
        'batch_deadline_seconds':1800,'retries':0,'market_only':True,'live_trading':False,
        'database_access':False,'research_acceptance':False,'vendor_basis':'unverified',
        'operator_policy':'fixed_completed_history_any_time',
        'preflight_sha256':REMAINING_PREFLIGHT_PIN,
        'manifest_sha256':MANIFEST_PIN,'calendar_sha256':CALENDAR_PIN}

def capture(plan_sha):
    proposed=plan()
    canonical=json.dumps(proposed,sort_keys=True,allow_nan=False).encode()
    if base.sha(canonical)!=plan_sha:raise base.StopCapture('reviewed_plan_hash_mismatch')
    runtime=preflight()
    out=HERE/'remaining_capture_identity24';out.mkdir(exist_ok=False)
    base.write_json(out/'plan.json',proposed)
    base.write_json(out/'initial_preflight.json',runtime)
    paths=[Path(__file__),HERE/'test_collect_remaining.py',HERE/'capture.py',HERE/'preflight.ps1',HERE/'preflight_residual27.ps1',MANIFEST,CALENDAR,
        HERE/'qualification_capture/producer_pins.json',HERE/'qualification_capture/summary.json']
    paths += [p for directory in ['identity_search_600289','identity_search_remaining23'] for p in (HERE/directory).iterdir() if p.is_file()]
    pins={str(p.resolve()):base.sha(p.read_bytes()) for p in paths}
    base.write_json(out/'producer_pins.json',pins)
    start=time.monotonic();attempts=0;stop=None
    for job in proposed['jobs']:
        if time.monotonic()-start+base.TIMEOUT>1800:stop='batch_deadline';break
        if attempts:time.sleep(base.INTERVAL)
        try:
            for path,pin in pins.items():
                if base.sha(Path(path).read_bytes())!=pin:raise base.StopCapture('producer_or_contract_changed')
            current=preflight()
            if current['endpoint_sha256']!=runtime['endpoint_sha256']:raise base.StopCapture('endpoint_generation_changed')
            token=base.credentials(current)
        except base.StopCapture as e:stop=str(e);break
        except (OSError,ValueError,subprocess.SubprocessError):stop='pre_request_metadata_failure';break
        if time.monotonic()-start+base.TIMEOUT>1800:
            del token
            stop='batch_deadline_after_preflight';break
        base.write_json(out/f"preflight_{job['id']}.json",current)
        base.write_json(out/f"request_{job['id']}.json",job['payload'])
        receipt={'job':job,'reserved_at':datetime.now(timezone.utc).isoformat(),'state':'reserved_before_http',
            'request_sha256':base.sha((out/f"request_{job['id']}.json").read_bytes())}
        base.write_json(out/f"attempt_{job['id']}.json",receipt)
        attempts+=1
        try:
            status,raw=base.fetch(job['payload'],token)
            with (out/f"response_{job['id']}.bin").open('xb') as f:f.write(raw)
            receipt.update(http_status=status,raw_sha256=base.sha(raw),raw_bytes=len(raw),observed_at=datetime.now(timezone.utc).isoformat())
            if status!=200:raise base.StopCapture(f'http_status_{status}')
            envelope=json.loads(raw)
            if envelope.get('ok') is not True:raise base.StopCapture('api_not_success')
            items=envelope['data']['items']
            if type(items) is not list or len(items)!=1:raise base.StopCapture('item_count_mismatch')
            identity=items[0]['security']
            if identity.get('hostFullCode')!=job['host_full_code']:raise base.StopCapture('native_identity_mismatch')
            points=items[0]['points']
            if not points:raise base.StopCapture('empty_points')
            receipt.update(state='received_unqualified',row_count=len(points),source_security=identity)
        except base.StopCapture as e:stop=str(e)
        except (OSError,http.client.HTTPException):stop='transport_failure_no_retry'
        except (ValueError,TypeError,KeyError,AttributeError):stop='invalid_response_shape'
        finally:
            del token
            receipt['stop_reason']=stop
            base.write_json(out/f"completed_{job['id']}.json",receipt)
            print(json.dumps({'job':job['id'],'symbol':job['symbol'],'rows':receipt.get('row_count'),
                'http_status':receipt.get('http_status'),'stop_reason':stop}),flush=True)
        if stop:break
    summary={'attempts':attempts,'unissued':24-attempts,'stop_reason':stop,'elapsed_seconds':time.monotonic()-start,
        'reused_instruments':28,'eligible':False,'live_trading':False,'database_access':False}
    base.write_json(out/'summary.json',summary);print(json.dumps(summary),flush=True)
    return int(bool(stop))

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--capture',action='store_true');parser.add_argument('--sha')
    args=parser.parse_args()
    try:
        if args.capture:raise SystemExit(capture(args.sha))
        value=plan();print(json.dumps({'plan':value,'canonical_sha256':base.sha(json.dumps(value,sort_keys=True,allow_nan=False).encode())},indent=2))
    except (base.StopCapture,FileExistsError) as e:
        print(json.dumps({'stopped':str(e) if isinstance(e,base.StopCapture) else 'existing_claim_no_resume'}));raise SystemExit(2)
