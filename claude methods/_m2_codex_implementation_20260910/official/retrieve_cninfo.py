"""Public filing metadata only; no market-price or local API requests."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
from urllib.parse import urlencode
import urllib.request

HERE = Path(__file__).resolve().parent
JOBS = [(f'cninfo_topsearch_{code}.json',
    'http://www.cninfo.com.cn/new/information/topSearch/detailOfQuery',
    {'keyWord':code,'maxNum':10}) for code in ['920002','920003','920005','920007']]
for year, interval in [('2023','2023-06-01~2023-07-10'),('2024','2024-05-01~2024-06-10')]:
    JOBS.append((f'cninfo_832000_cash_{year}_query.json',
        'http://www.cninfo.com.cn/new/hisAnnouncement/query',
        dict(tabName='fulltext',pageSize=30,pageNum=1,column='sse',category='',plate='',
             seDate=interval,searchkey='',sortName='',sortType='',isHLtitle='true',stock='920000,gfbj0832000')))


def run(job):
    name,url,body=job
    row=dict(file=name,url=url,body=body,started_at=datetime.now(timezone.utc).isoformat())
    try:
        request=urllib.request.Request(url,data=urlencode(body).encode(),headers={'User-Agent':'Mozilla/5.0','Referer':'http://www.cninfo.com.cn/'})
        with urllib.request.urlopen(request,timeout=15) as response:
            raw=response.read(2*1024*1024+1)
            if len(raw)>2*1024*1024: raise ValueError('response too large')
            json.loads(raw)
            with (HERE/name).open('xb') as output: output.write(raw)
            row.update(status=response.status,raw_sha256=sha256(raw).hexdigest(),bytes=len(raw))
    except Exception as exc: row.update(error_type=type(exc).__name__,error=str(exc))
    row['completed_at']=datetime.now(timezone.utc).isoformat()
    return row


if __name__=='__main__':
    if (HERE/'retrieval_cninfo.json').exists(): raise SystemExit('already executed')
    with ThreadPoolExecutor(max_workers=3) as pool: rows=list(pool.map(run,JOBS))
    with (HERE/'retrieval_cninfo.json').open('x',encoding='utf-8') as output: json.dump(rows,output,ensure_ascii=False,indent=2)
    print(json.dumps(rows,ensure_ascii=True,indent=2))
