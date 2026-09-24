"""Bounded retrieval of named public exchange/disclosure documents only."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import urllib.request

HERE = Path(__file__).resolve().parent
SOURCES = [
    ('sse_csi300_method.html', 'http://www.sse.com.cn/market/sseindex/diclosure/c/c_20150911_3984891.shtml'),
    ('bse_920002_listing_v2.pdf', 'https://www.bse.cn/disclosure/2024/2024-05-27/1716806648_649247.pdf'),
    ('bse_920003_listing_news.html', 'https://www.bseinfo.net/issue_report_meeting/200027058.html'),
    ('bse_920005_listing_news.html', 'https://www.bse.cn/issue_report_meeting/200026402.html'),
    ('bse_920007_listing_v2.pdf', 'http://www.bse.cn/disclosure/2025/2025-08-05/1754388734_778470.pdf'),
    ('cninfo_832000_2023_annual_report.pdf', 'https://static.cninfo.com.cn/finalpage/2024-04-26/1219889379.PDF'),
]


def retrieve(source):
    name, url = source
    row = dict(file=name, url=url, started_at=datetime.now(timezone.utc).isoformat(), attempts=1)
    try:
        request = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(request, timeout=12) as response:
            raw = response.read(16*1024*1024+1)
            if len(raw) > 16*1024*1024:
                raise ValueError('too large')
            with (HERE/name).open('xb') as output:
                output.write(raw)
            row.update(status=response.status, served_url=response.url, raw_sha256=sha256(raw).hexdigest(), bytes=len(raw), content_type=response.headers.get('Content-Type'))
    except Exception as exc:
        row.update(error_type=type(exc).__name__, error=str(exc))
    row['completed_at'] = datetime.now(timezone.utc).isoformat()
    return row


if __name__ == '__main__':
    if (HERE/'retrieval_v2.json').exists():
        raise SystemExit('already executed')
    with ThreadPoolExecutor(max_workers=3) as pool:
        rows = list(pool.map(retrieve, SOURCES))
    with (HERE/'retrieval_v2.json').open('x', encoding='utf-8') as output:
        json.dump(rows, output, ensure_ascii=False, indent=2)
    print(json.dumps(rows, ensure_ascii=True, indent=2))
