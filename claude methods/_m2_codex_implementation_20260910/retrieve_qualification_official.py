"""One-shot, public official documents only. Never accesses local market APIs."""
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import urllib.request
from urllib.parse import urlparse

HERE = Path(__file__).resolve().parent
SOURCES = [
    ('sse_csi300_method.html', 'https://www.sse.com.cn/market/sseindex/diclosure/c/c_20150911_3984891.shtml'),
    ('bse_920002_listing.pdf', 'https://www.bse.cn/disclosure/2024/2024-05-27/1716806650_280194.pdf'),
    ('bse_920003_listing.pdf', 'https://www.bse.cn/disclosure/2025/2025-11-04/1762250648_398373.pdf'),
    ('bse_920005_listing.html', 'https://www.bse.cn/issue_report_meeting/200026402.html'),
    ('bse_920007_listing.pdf', 'https://www.bse.cn/disclosure/2025/2025-08-05/1754388734_778470.pdf'),
]

class SameOfficialHost(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if urlparse(newurl).scheme != 'https' or urlparse(newurl).hostname != urlparse(req.full_url).hostname:
            raise ValueError('cross-host or non-TLS redirect refused')
        return super().redirect_request(req, fp, code, msg, headers, newurl)

def main():
    dest = HERE / 'official'
    dest.mkdir(exist_ok=True)
    receipt = dest / 'retrieval_qualification.json'
    if receipt.exists() or any((dest / name).exists() for name, _ in SOURCES):
        raise SystemExit('one-shot destination already has artifacts')
    results = []
    opener = urllib.request.build_opener(SameOfficialHost())
    for name, url in SOURCES:
        row = {'file':name, 'requested_url':url, 'started_at_utc':datetime.now(timezone.utc).isoformat(), 'attempts':1}
        try:
            request = urllib.request.Request(url, headers={'User-Agent':'Mozilla/5.0 (M2 independent evidence review)'})
            with opener.open(request, timeout=30) as response:
                raw = response.read(8 * 1024 * 1024 + 1)
                if len(raw) > 8 * 1024 * 1024:
                    raise ValueError('response too large')
                row.update(status=response.status, served_url=response.url,
                           content_type=response.headers.get('Content-Type'), bytes=len(raw), sha256=sha256(raw).hexdigest())
                (dest / name).write_bytes(raw)
        except Exception as exc:
            row['error_type'] = type(exc).__name__
            row['error'] = str(exc)
        row['completed_at_utc'] = datetime.now(timezone.utc).isoformat()
        results.append(row)
        print(json.dumps(row, ensure_ascii=False))
    receipt.write_text(json.dumps({'schema':'m2.official_document_retrieval.v1','results':results}, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')

if __name__ == '__main__':
    main()
