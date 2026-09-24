from pathlib import Path
import json, hashlib
from datetime import datetime, timezone
ROOT=Path(__file__).resolve().parents[3]
BASE=ROOT/'claude methods/_m4_20260912'
OUT=BASE/'codex/risk_review_01'
def sha(p):
    with p.open('rb') as f: return hashlib.file_digest(f,'sha256').hexdigest()
manifest_path=BASE/'claude_02b/artifact_manifest.json'
raw=manifest_path.read_bytes()
manifest=json.loads(raw)
checks={}
for label,pins in [('written',manifest['written']),('sources_read',manifest['sources_read']),('portfolio_freeze',json.loads((BASE/'portfolio_freeze.json').read_text('utf-8'))['pins']),('execution_freeze',json.loads((BASE/'execution_freeze.json').read_text('utf-8'))['pins']),('tracked',json.loads((BASE/'baseline/tracked_files_before.json').read_text('utf-8'))),('immutable',json.loads((BASE/'baseline/immutable_pins.json').read_text('utf-8')))]:
    failures=[]
    for rel,pin in pins.items():
        expected=pin['sha256'] if isinstance(pin,dict) else pin
        p=ROOT/rel
        if not p.exists() or sha(p)!=expected: failures.append(rel)
    checks[label]=dict(count=len(pins),failures=failures)
prod=json.loads((BASE/'baseline/production_files_before.json').read_text('utf-8'))
failures=[]
for path,before in prod.items():
    p=Path(path)
    now={'exists':p.exists()}
    if p.exists():
        s=p.stat(); now.update(sha256=sha(p),size=s.st_size,mtime_ns=s.st_mtime_ns)
    if now!=before: failures.append(path)
checks['production_positions']=dict(count=len(prod),failures=failures)
(OUT/'claude_delivery_01_manifest.json').write_bytes(raw)
receipt=dict(at_utc=datetime.now(timezone.utc).isoformat(),manifest_sha256=hashlib.sha256(raw).hexdigest(),checks=checks,all_preserved=not any(c['failures'] for c in checks.values()),sqlite_connections=0)
(OUT/'delivery_verification.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(receipt,ensure_ascii=False,indent=2))
