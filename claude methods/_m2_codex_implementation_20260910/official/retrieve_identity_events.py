"""Named public filing queries and implementation documents; no local endpoint."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timezone
from hashlib import sha256
import json
from pathlib import Path
from urllib.parse import urlencode
import urllib.request

HERE=Path(__file__).resolve().parent
JOBS=[
 ('cninfo_832000_2023_cash_implementation.pdf','https://static.cninfo.com.cn/finalpage/2023-06-26/1217139649.PDF',None),
 ('cninfo_832000_2024_cash_implementation.pdf','https://static.cninfo.com.cn/finalpage/2024-05-29/1220197112.PDF',None),
]
for code,interval in [('920002','2024-05-24~2024-05-30'),('920003','2025-11-01~2025-11-08'),('920005','2025-07-25~2025-08-01'),('920007','2025-08-01~2025-08-09')]:
 JOBS.append((f'cninfo_{code}_listing_query.json','http://www.cninfo.com.cn/new/hisAnnouncement/query',
  dict(tabName='fulltext',pageSize=30,pageNum=1,column='sse',category='',plate='',seDate=interval,searchkey=code,sortName='',sortType='',isHLtitle='false',stock='')))

def run(job):
 name,url,body=job;row=dict(file=name,url=url,body=body,started_at=datetime.now(timezone.utc).isoformat())
 try:
  req=urllib.request.Request(url,data=urlencode(body).encode() if body else None,headers={'User-Agent':'Mozilla/5.0','Referer':'http://www.cninfo.com.cn/'})
  with urllib.request.urlopen(req,timeout=15) as response:
   raw=response.read(8*1024*1024+1)
   if len(raw)>8*1024*1024:raise ValueError('too large')
   if body:json.loads(raw)
   elif not raw.startswith(b'%PDF'):raise ValueError('not a PDF')
   with (HERE/name).open('xb') as output:output.write(raw)
   row.update(status=response.status,raw_sha256=sha256(raw).hexdigest(),bytes=len(raw))
 except Exception as exc:row.update(error_type=type(exc).__name__,error=str(exc))
 row['completed_at']=datetime.now(timezone.utc).isoformat();return row

if __name__=='__main__':
 if (HERE/'retrieval_identity_events.json').exists():raise SystemExit('already executed')
 with ThreadPoolExecutor(max_workers=3) as pool:rows=list(pool.map(run,JOBS))
 with (HERE/'retrieval_identity_events.json').open('x',encoding='utf-8') as output:json.dump(rows,output,ensure_ascii=False,indent=2)
 print(json.dumps(rows,ensure_ascii=True,indent=2))
