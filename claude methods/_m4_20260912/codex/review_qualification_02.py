from pathlib import Path
import hashlib, json, sys, importlib.util
from datetime import datetime, timezone
ROOT=Path(__file__).resolve().parents[3]
BASE=ROOT/'claude methods/_m4_20260912'
SRC=BASE/'claude_03a'
OUT=BASE/'codex/qualification_review_02'
OUT.mkdir(exist_ok=True)
assert not any(p.is_file() for p in OUT.rglob('*')), 'Refuse to overwrite review files'
(OUT/'evidence').mkdir(exist_ok=True)
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p): return json.loads(p.read_text('utf-8-sig'))
manifest=read(SRC/'artifact_manifest.json')
checks={}
for label,pins in [('written',manifest['written']),('sources_read',manifest['consumed']), *[(n,read(BASE/n)['pins']) for n in ['execution_freeze.json','portfolio_freeze.json','risk_freeze.json']],('tracked',read(BASE/'baseline/tracked_files_before.json')),('immutable',read(BASE/'baseline/immutable_pins.json'))]:
    failures=[]
    for rel,pin in pins.items():
        p=ROOT/rel; expected=pin['sha256'] if isinstance(pin,dict) else pin
        if not p.exists() or sha(p)!=expected: failures.append(rel)
    checks[label]={'count':len(pins),'failures':failures}
prod=read(BASE/'baseline/production_files_before.json'); failures=[]
for path,before in prod.items():
    p=Path(path); now={'exists':p.exists()}
    if p.exists():
        st=p.stat(); now.update(sha256=sha(p),size=st.st_size,mtime_ns=st.st_mtime_ns)
    if now!=before: failures.append(path)
checks['production_positions']={'count':len(prod),'failures':failures}
for n in ['artifact_manifest.json','qualification.json','QUALIFICATION_MATRIX.md','NEXT_READ_PROPOSAL.md','validate_qualification.py','proposal_mapping.py','CORRECTION_MATRIX.md']:
    (OUT/n).write_bytes((SRC/n).read_bytes())
verification={'at_utc':datetime.now(timezone.utc).isoformat(),'manifest_sha256':sha(SRC/'artifact_manifest.json'),'checks':checks,'all_preserved':not any(v['failures'] for v in checks.values()),'sqlite_connections':0}
(OUT/'verification.json').write_text(json.dumps(verification,ensure_ascii=False,indent=2),encoding='utf-8')
spec=importlib.util.spec_from_file_location('qualification_validator',SRC/'validate_qualification.py')
v=importlib.util.module_from_spec(spec); sys.modules[spec.name]=v; spec.loader.exec_module(v)
# Execute unchanged validator functions; redirect only its input copies and all output paths to Codex-owned review.
v.HERE=OUT; v.EVIDENCE=OUT/'evidence'; v.ALLOWED_WRITE_ROOT=OUT.resolve()
rc=v.main()
receipt={'actual_command':sys.argv,'validator_original_sha256':sha(SRC/'validate_qualification.py'),'validator_snapshot_sha256':sha(OUT/'validate_qualification.py'),'adaptation':'Only HERE/EVIDENCE/ALLOWED_WRITE_ROOT redirected; PROJECT/M4/source pins and function bodies unchanged. No Claude output overwritten.','exit_code':rc,'all_preserved':verification['all_preserved']}
(OUT/'replay_receipt.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'verification':verification,'replay':receipt},ensure_ascii=False))
sys.exit(rc)


