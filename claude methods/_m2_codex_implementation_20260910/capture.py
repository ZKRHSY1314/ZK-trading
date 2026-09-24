"""Bounded market-only evidence transport; never opens a database.

Each reviewed plan is supplied with its exact SHA. New plans have separate
durable claims; unsuccessful runs are never resumed or overwritten.
"""
from __future__ import annotations
import argparse
import base64
from datetime import datetime, timezone
import hashlib
import http.client
import importlib.util
import json
from pathlib import Path
import re
import socket
import subprocess
import threading
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
PRIOR = HERE.parent / '_m2_codex_review/tonghuasun_static_20260909'
HOME = Path(r'D:\TonghuasunCodex')
PW = Path(r'C:\Users\Administrator\.cache\codex-runtimes\codex-primary-runtime\dependencies\native\powershell\pwsh.exe')
ROUTE = '/api/v2/quotes/candle'
TIMEOUT, MAX_BYTES, INTERVAL = 30.0, 8 * 1024 * 1024, 1.5

class StopCapture(Exception):
    pass

def sha(raw):
    return hashlib.sha256(raw).hexdigest()

def write_json(path, data):
    import os
    with Path(path).open('x', encoding='utf-8', newline='\n') as f:
        json.dump(data, f, ensure_ascii=False, indent=2, allow_nan=False)
        f.write('\n')
        f.flush()
        os.fsync(f.fileno())

def read_plan(path, expected_sha):
    raw = Path(path).read_bytes()
    if sha(raw) != expected_sha:
        raise StopCapture('plan_hash_mismatch')
    plan = json.loads(raw)
    if plan['kind'] != 'qualification' or plan['max_attempts'] != 8 or len(plan['jobs']) != 8:
        raise StopCapture('unsupported_plan')
    expected = [('SH000300','USZI399300',0),('SH000001','USHI1A0001',0)]
    expected += [(s,h,a) for s,h in [('SH600011','USHA600011'),('BJ920000','USTM920000')] for a in (0,1,2)]
    for i,(job,(symbol,host,adjust)) in enumerate(zip(plan['jobs'],expected),1):
        payload = {'market':1,'security':{'hostFullCode':host},
            'startTimeUtc':'2022-08-23T16:00:00Z','endTimeUtc':'2026-09-04T15:59:59.999Z',
            'limit':5000,'fields':['full_code','security_name','open','high','low','latest',
            'transaction_volume','transaction_amount','date_time'],'period':7,'adjustment':adjust}
        expected_job = {'id':i,'symbol':symbol,'host_full_code':host,'payload':payload}
        canonical = lambda value: json.dumps(value,sort_keys=True,allow_nan=False)
        if canonical(job) != canonical(expected_job):
            raise StopCapture('job_not_in_reviewed_plan')
    if plan.get('live_trading') is not False or plan.get('database_access') is not False:
        raise StopCapture('safety_contract_mismatch')
    return plan

def preflight():
    guard_path = PRIOR / 'endpoint_identity_guard.py'
    if sha(guard_path.read_bytes()) != 'db6c3b6d4dc385cc39a05ad6a8d5cc1d0019d2a2b5988e0af22eea1a637b6483':
        raise StopCapture('identity_guard_pin_mismatch')
    spec = importlib.util.spec_from_file_location('m2_endpoint_guard', guard_path)
    guard = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(guard)
    script = HERE / 'preflight.ps1'
    encoded = base64.b64encode(script.read_text(encoding='utf-8-sig').encode('utf-16le')).decode('ascii')
    p = subprocess.run([str(PW),'-NoProfile','-NonInteractive','-EncodedCommand',encoded],
        capture_output=True, timeout=30, encoding='utf-8-sig')
    if p.returncode:
        raise StopCapture('runtime_inventory_failed')
    try:
        metadata = json.loads(p.stdout)
        endpoint_path = HOME / 'runtime/endpoint.json'
        endpoint_raw = endpoint_path.read_bytes()
        endpoint = json.loads(endpoint_raw)
        host = metadata['host_process']
        result = guard.validate_endpoint_identity(endpoint,current_pid=host['pid'],
            host_created_at=host['started_utc'],
            endpoint_mtime=datetime.fromtimestamp(endpoint_path.stat().st_mtime,timezone.utc))
        if metadata.get('passed') is not True or result['passed'] is not True:
            raise StopCapture('runtime_identity_not_ready')
        metadata['endpoint_identity'] = result
        metadata['endpoint_sha256'] = sha(endpoint_raw)
        return metadata
    except (ValueError, TypeError, KeyError, OSError):
        raise StopCapture('runtime_metadata_unusable') from None

def credentials(runtime):
    # Endpoint identity was established before any token-bearing configuration read.
    endpoint_path = HOME / 'runtime/endpoint.json'
    if sha(endpoint_path.read_bytes()) != runtime['endpoint_sha256']:
        raise StopCapture('endpoint_generation_changed')
    try:
        config = json.loads((HOME/'config.json').read_bytes())
    except (ValueError, OSError):
        raise StopCapture('configuration_unavailable') from None
    if config.get('enableTradeTools') is not False or config.get('enableAutomatedTradeApi') is not False:
        raise StopCapture('trading_flags_not_false')
    if config.get('preferredPort') != 17180:
        raise StopCapture('configuration_port_mismatch')
    token = config.get('localAccessToken')
    if not isinstance(token,str) or not re.fullmatch('[a-fA-F0-9]{64}',token):
        raise StopCapture('credential_shape_invalid')
    return token

def fetch(payload, token):
    deadline = time.monotonic()+TIMEOUT
    conn = http.client.HTTPConnection('127.0.0.1',17180,timeout=TIMEOUT)
    holder = [None]
    expired = threading.Event()
    def abort():
        expired.set()
        if holder[0] is not None:
            try: holder[0].shutdown(socket.SHUT_RDWR)
            except OSError: pass
    watchdog = threading.Timer(TIMEOUT,abort)
    watchdog.daemon=True
    watchdog.start()
    try:
        conn.connect()
        sock = holder[0] = conn.sock
        def budget():
            remaining = deadline-time.monotonic()
            if remaining <= 0 or expired.is_set():
                raise StopCapture('absolute_request_deadline')
            sock.settimeout(remaining)
        budget()
        conn.request('POST',ROUTE,json.dumps(payload).encode('utf-8'),
            {'Content-Type':'application/json','Accept':'application/json','Accept-Encoding':'identity',
             'X-Tonghuasun-Codex-Token':token,'User-Agent':'m2-codex-qualified-history'})
        budget()
        response = conn.getresponse()
        chunks,size=[],0
        while True:
            budget()
            chunk = response.read1(min(65536,MAX_BYTES+1-size))
            if not chunk: break
            chunks.append(chunk)
            size+=len(chunk)
            if size>MAX_BYTES: raise StopCapture('response_size_limit')
        raw=b''.join(chunks)
        if token.lower().encode('ascii') in raw.lower():
            raise StopCapture('credential_echo_not_retained')
        budget()
        return response.status,raw
    finally:
        watchdog.cancel()
        conn.close()

def capture(plan_path,expected_sha):
    plan = read_plan(plan_path,expected_sha)
    runtime = preflight()
    out=HERE/'qualification_capture'
    out.mkdir(exist_ok=False)
    write_json(out/'plan.json',plan)
    write_json(out/'initial_preflight.json',runtime)
    paths=[Path(__file__),HERE/'preflight.ps1',HERE/'test_capture.py',Path(plan_path),PRIOR/'endpoint_identity_guard.py']
    write_json(out/'producer_pins.json',{str(p.resolve()):sha(p.read_bytes()) for p in paths})
    start=time.monotonic()
    attempted=0
    stop=None
    for job in plan['jobs']:
        if time.monotonic()-start+TIMEOUT>600:
            stop='batch_deadline'; break
        if attempted: time.sleep(INTERVAL)
        # Recheck process+queue+endpoint generation before every authenticated request.
        try:
            current=preflight()
            if current['endpoint_sha256'] != runtime['endpoint_sha256']:
                raise StopCapture('endpoint_generation_changed')
            token=credentials(current)
        except StopCapture as e:
            stop=str(e); break
        except (OSError,ValueError,subprocess.SubprocessError):
            stop='pre_request_metadata_failure'; break
        if time.monotonic()-start+TIMEOUT>600:
            del token
            stop='batch_deadline_after_preflight'; break
        write_json(out/f"preflight_{job['id']}.json",current)
        attempted+=1
        receipt={'job':job,'reserved_at':datetime.now(timezone.utc).isoformat(),'state':'reserved_before_http'}
        write_json(out/f"attempt_{job['id']}.json",receipt)
        try:
            status,raw=fetch(job['payload'],token)
            with (out/f"response_{job['id']}.bin").open('xb') as f: f.write(raw)
            receipt.update(http_status=status,raw_sha256=sha(raw),raw_bytes=len(raw),observed_at=datetime.now(timezone.utc).isoformat())
            if status!=200: raise StopCapture(f'http_status_{status}')
            data=json.loads(raw)
            if data.get('ok') is not True: raise StopCapture('api_not_success')
            items=data['data']['items']
            if len(items)!=1: raise StopCapture('security_item_count_mismatch')
            identity=items[0]['security']
            if identity.get('hostFullCode')!=job['host_full_code']: raise StopCapture('native_identity_mismatch')
            points=items[0]['points']
            if not points: raise StopCapture('empty_points')
            receipt.update(state='received_unqualified',row_count=len(points),source_security=identity,vendor_basis='unverified')
        except StopCapture as e: stop=str(e)
        except (OSError,http.client.HTTPException): stop='transport_failure_no_retry'
        except (ValueError,KeyError,TypeError): stop='invalid_response_shape'
        finally:
            del token
            receipt['stop_reason']=stop
            write_json(out/f"completed_{job['id']}.json",receipt)
            print(json.dumps({k:receipt.get(k) for k in ('state','http_status','row_count','source_security','stop_reason')},ensure_ascii=True),flush=True)
        if stop: break
    summary={'attempts':attempted,'unissued':8-attempted,'stop_reason':stop,
        'elapsed_seconds':time.monotonic()-start,'eligible':False,'live_trading':False,'database_access':False}
    write_json(out/'summary.json',summary)
    print(json.dumps(summary),flush=True)
    return int(bool(stop))

if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--plan',type=Path,required=True)
    p.add_argument('--sha',required=True)
    p.add_argument('--capture',action='store_true')
    a=p.parse_args()
    try:
        if a.capture: raise SystemExit(capture(a.plan,a.sha))
        print(json.dumps(read_plan(a.plan,a.sha),ensure_ascii=False,indent=2))
    except (StopCapture,FileExistsError) as e:
        print(json.dumps({'stopped':str(e) if isinstance(e,StopCapture) else 'existing_claim_no_resume'}))
        raise SystemExit(2)
