"""One market-security identity lookup for the retained empty SH600289 series."""
from pathlib import Path
from datetime import datetime, timezone
import json
import collect_residual27 as reviewed

HERE=Path(__file__).resolve().parent
if __name__=='__main__':
    runtime=reviewed.preflight()
    out=HERE/'identity_search_600289';out.mkdir(exist_ok=False)
    request={'market':1,'query':'600289','limit':5}
    reviewed.base.write_json(out/'request.json',request)
    reviewed.base.write_json(out/'preflight.json',runtime)
    reviewed.base.write_json(out/'producer.json',{'script_sha256':reviewed.base.sha(Path(__file__).read_bytes()),
        'transport_sha256':reviewed.base.sha((HERE/'capture.py').read_bytes()),
        'guard_sha256':reviewed.base.sha((HERE/'preflight_residual27.ps1').read_bytes()),
        'route':'/api/v2/securities/search','max_requests':1,'retries':0,'live_trading':False})
    token=reviewed.base.credentials(runtime)
    reviewed.base.ROUTE='/api/v2/securities/search'
    try:
        status,raw=reviewed.base.fetch(request,token)
    finally:del token
    with (out/'response.bin').open('xb') as handle:handle.write(raw)
    reviewed.base.write_json(out/'receipt.json',{'status':status,'raw_sha256':reviewed.base.sha(raw),
        'at_utc':datetime.now(timezone.utc).isoformat(),'market_metadata_only':True})
    print(json.dumps({'status':status,'response':json.loads(raw)},ensure_ascii=True))
