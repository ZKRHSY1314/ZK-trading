"""Bounded current market identity evidence for 23 unissued pilot securities."""
from pathlib import Path
from datetime import datetime, timezone
import json,time
import collect_residual27 as reviewed

HERE=Path(__file__).resolve().parent
if __name__=='__main__':
    jobs=reviewed.plan()['jobs'][4:]
    if len(jobs)!=23 or [jobs[0]['id'],jobs[-1]['id']]!=[26,48]:raise SystemExit('wrong residual')
    runtime=reviewed.preflight()
    out=HERE/'identity_search_remaining23';out.mkdir(exist_ok=False)
    reviewed.base.write_json(out/'plan.json',{'jobs':jobs,'route':'/api/v2/securities/search','limit':5,'max_requests':23,'retries':0,'live_trading':False})
    reviewed.base.write_json(out/'producer.json',{str(HERE/name):reviewed.base.sha((HERE/name).read_bytes()) for name in
        ('search_remaining_identities.py','capture.py','collect_residual27.py','preflight_residual27.ps1')})
    reviewed.base.ROUTE='/api/v2/securities/search'
    completed=[];start=time.monotonic()
    for job in jobs:
        if time.monotonic()-start>600:raise SystemExit('batch deadline')
        if completed:time.sleep(1.5)
        current=reviewed.preflight()
        if current['endpoint_sha256']!=runtime['endpoint_sha256']:raise SystemExit('endpoint changed')
        request={'market':1,'query':job['symbol'][2:],'limit':5}
        reviewed.base.write_json(out/f"request_{job['id']}.json",request)
        reviewed.base.write_json(out/f"preflight_{job['id']}.json",current)
        token=reviewed.base.credentials(current)
        try:status,raw=reviewed.base.fetch(request,token)
        finally:del token
        with (out/f"response_{job['id']}.bin").open('xb') as handle:handle.write(raw)
        receipt={'symbol':job['symbol'],'status':status,'raw_sha256':reviewed.base.sha(raw),'at_utc':datetime.now(timezone.utc).isoformat()}
        reviewed.base.write_json(out/f"receipt_{job['id']}.json",receipt)
        if status!=200:raise SystemExit('search HTTP failed')
        result=json.loads(raw)
        if result.get('ok') is not True:raise SystemExit('search response failed')
        full=job['symbol'][2:]+'.'+job['symbol'][:2]
        found=[s for s in result['data']['items'] if s.get('fullCode')==full]
        if len(found)!=1:raise SystemExit('exact source identity not unique')
        completed.append({'job_id':job['id'],'symbol':job['symbol'],'security':found[0],'raw_sha256':receipt['raw_sha256']})
        print(json.dumps(completed[-1],ensure_ascii=True),flush=True)
    reviewed.base.write_json(out/'summary.json',{'identities':completed,'requests':len(completed),'market_metadata_only':True})
