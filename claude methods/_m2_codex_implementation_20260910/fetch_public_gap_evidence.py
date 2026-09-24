"""Bounded public disclosure retrieval, separate from all market capture runners.

No credentials, retries, production access, acceptance decisions or transformations.
Only the two public CNInfo endpoints already inspected in local AkShare are used.
"""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import urllib.parse
import urllib.request

HERE = Path(__file__).resolve().parent / "gap_evidence"


def fetch(name, url, payload=None):
    target = HERE / name
    if target.exists() or target.with_suffix(target.suffix + ".receipt.json").exists():
        raise ValueError("existing evidence is immutable")
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme != "https" or parsed.hostname not in {"www.cninfo.com.cn", "static.cninfo.com.cn"}:
        raise ValueError("public disclosure host not allowlisted")
    body = None if payload is None else urllib.parse.urlencode(payload).encode()
    receipt = {"url": url, "payload": payload, "at_utc": datetime.now(timezone.utc).isoformat(),
               "producer_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
               "retry_count": 0, "credentials": False}
    try:
        request = urllib.request.Request(url, data=body, headers={"User-Agent": "Mozilla/5.0", "Referer": "https://www.cninfo.com.cn/"})
        with urllib.request.urlopen(request, timeout=12) as response:
            raw = response.read(8 * 1024 * 1024 + 1)
            if len(raw) > 8 * 1024 * 1024:
                raise ValueError("public evidence over byte cap")
            if name.endswith(".pdf") and not raw.startswith(b"%PDF"):
                raise ValueError("not PDF bytes")
            data = None if name.endswith(".pdf") else json.loads(raw)
            with target.open("xb") as handle:
                handle.write(raw)
            receipt.update(status=response.status, bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())
    except Exception as exc:
        receipt.update(status="failed", error=type(exc).__name__)
        data = None
    with target.with_suffix(target.suffix + ".receipt.json").open("x", encoding="utf-8") as handle:
        json.dump(receipt, handle, indent=2)
    return data, receipt


def search(code, keyword, start, end, name):
    mapping = json.loads((HERE / "cninfo_stock_identity.json").read_bytes())
    orgs = {x["code"]: x["orgId"] for x in mapping["stockList"]}
    payload = {"pageNum": "1", "pageSize": "100", "column": "szse", "tabName": "fulltext", "plate": "",
               "stock": code + "," + orgs[code], "searchkey": keyword, "secid": "", "category": "", "trade": "",
               "seDate": start + "~" + end, "sortName": "", "sortType": "", "isHLtitle": "false"}
    data, receipt = fetch(name, "https://www.cninfo.com.cn/new/hisAnnouncement/query", payload)
    if data is None:
        return receipt
    return {"symbol": code, "total": data.get("totalAnnouncement"), "returned": len(data.get("announcements") or []),
            "items": [{k: row.get(k) for k in ("secCode", "announcementTitle", "adjunctUrl")} for row in data.get("announcements") or []]}
