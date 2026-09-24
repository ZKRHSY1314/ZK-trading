"""Independent G-3 review: retained files and temporary negative fixtures only."""
import contextlib
import copy
import hashlib
import io
import json
from pathlib import Path
import runpy
import shutil
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
SMOKE = ROOT/'claude methods/_m2_smoke'
ANALYSIS = SMOKE/'g3_ratio_analysis_20260909'
REVIEW = Path(__file__).resolve().parent
BLOCKED = []

def audit(event, args):
    if event in {'sqlite3.connect', 'subprocess.Popen', 'os.system'}:
        BLOCKED.append(event)
        raise RuntimeError('offline review prohibits '+event)
    if event in {'socket.connect','socket.bind','socket.getaddrinfo'}:
        endpoint = args[1] if event != 'socket.getaddrinfo' else args[0]
        host = endpoint[0] if isinstance(endpoint, tuple) else endpoint
        if host not in {'127.0.0.1', '::1', 'localhost'}:
            BLOCKED.append(event)
            raise RuntimeError('offline review prohibits remote socket use')

sys.addaudithook(audit)
sys.dont_write_bytecode = True
sys.path[:0] = [str(ANALYSIS), str(SMOKE)]

def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p): return json.loads(p.read_text(encoding='utf-8'))
def write(p, obj): p.write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding='utf-8')
def tree(): return {p.relative_to(ROOT).as_posix():sha(p) for p in SMOKE.rglob('*') if p.is_file() and '__pycache__' not in p.parts}

before=tree()
prior=read(REVIEW/'basis_handoff_docs_review_r2_snapshot.json')['protected_after']
prior_drift=[p for p,h in prior.items() if not (ROOT/p).is_file() or sha(ROOT/p)!=h]
output=io.StringIO()
with contextlib.redirect_stdout(output):
    try:
        runpy.run_path(str(ANALYSIS/'test_g3_ratio_analysis.py'),run_name='__main__')
        suite_exit=0
    except SystemExit as e: suite_exit=e.code

import g3_ratio_analysis as g3
import smoke_capture as cap
import basis_record as br
checks=[]
def expect(name,condition,detail=None): checks.append({'name':name,'passed':bool(condition),'detail':detail})

stored=read(ANALYSIS/'results.json')
with cap.no_remote_connections('Codex G3 prohibits network'), cap.db_guard('Codex G3 prohibits database'):
    verified=br.verify(g3.DEFAULT_REVISION)
    manifest,extract,vendor=g3.load_inputs()
    fresh=g3.analyse(manifest,extract,vendor)
    expect('current selected revision passes independently reviewed verifier',not verified['pins_stale'],verified['deterministic_sha256'])
    expect('all analysis result fields reproduce',stored['results']==fresh)
    # main renders before JSON sort_keys serialization; reconstruct its insertion order.
    render_payload=dict(stored,results=fresh,documented_segments=g3.documented_470_row_segments(fresh))
    expect('report regenerates exactly',g3.render_report(render_payload)==(ANALYSIS/'REPORT.md').read_text(encoding='utf-8'))
    expect('all recorded input hashes match',all(sha(g3.DEFAULT_REVISION/name)==h for name,h in stored['inputs']['input_hashes'].items()),len(stored['inputs']['input_hashes']))
    expect('recorded producer hashes match',all(sha((ANALYSIS if name=='g3_ratio_analysis.py' else SMOKE)/name)==h for name,h in stored['code_hashes'].items()),stored['code_hashes'])
    for name,symbol,count in [('sh600011','SH600011',538),('bj920000','BJ920000',501),('sh000300','SH000300',538)]:
        block=stored['results'][name]
        vmap={r['date']:r['close'] for r in vendor[name]['rows']}
        refs=extract['rows'][symbol];ref={r['trade_date']:r['close'] for r in refs}
        expected=[[d,vmap[d]/ref[d]] for d in sorted(set(vmap)&set(ref))]
        expect(name+' independent ratio join',expected==block['comparison']['ratio']['series'] and len(expected)==count,count)
        difference=[[d,round(vmap[d]-ref[d],10)] for d in sorted(set(vmap)&set(ref))]
        expect(name+' independent price differences',difference==block['comparison']['difference']['series'])
        chunks=[]
        for r in sorted(refs,key=lambda x:x['trade_date']):
            key=(r['source'],r['updated_at'])
            if not chunks or chunks[-1]['key']!=key:chunks.append({'key':key,'dates':[]})
            chunks[-1]['dates'].append(r['trade_date'])
        wanted=[(*s['key'],len(s['dates']),s['dates'][0],s['dates'][-1]) for s in chunks]
        actual=[(s['key']['source'],s['key']['updated_at'],s['rows'],s['first_date'],s['last_date']) for s in block['boundaries']['source_and_updated_at_segments']]
        expect(name+' independent segment partition',wanted==actual,[s[2] for s in actual])
    # End-to-end invalid-value probes: the report should describe invalid prices,
    # rather than crashing or allowing them only in segment statistics.
    for value,label in [(None,'null'),(True,'boolean'),(float('inf'),'infinity')]:
        bad=copy.deepcopy(extract);date=bad['rows']['SH600011'][0]['trade_date'];bad['rows']['SH600011'][0]['close']=value
        try:
            result=g3.analyse(manifest,bad,vendor)['sh600011']
            ok=(date in result['comparison']['invalid_reference_closes'] and sum(s['compared_dates'] for s in result['segments'])==result['comparison']['compared_dates'])
            detail={'invalid_dates':result['comparison']['invalid_reference_closes'],'global_compared':result['comparison']['compared_dates'],'segment_compared':sum(s['compared_dates'] for s in result['segments'])}
        except Exception as e:ok=False;detail={'exception':type(e).__name__,'message':str(e)}
        expect(label+' invalid reference is reported consistently end to end',ok,detail)
    expect('daily ratio change output is present',all(any(k in b['comparison'] for k in ('changes','daily_changes','ratio_changes')) or 'changes' in b['comparison']['ratio'] for b in stored['results'].values()),'Current output has level ratios and vendor-reference differences, but no consecutive-date change records.')

expect('prior checkpoint unchanged',not prior_drift,prior_drift)
after=tree();expect('all smoke and analysis files preserved during review',before==after,len(before))
summary={'suite_exit':suite_exit,'suite_stdout':output.getvalue(),'checks':checks,'passed':sum(c['passed'] for c in checks),'total':len(checks),'blocked_operations':BLOCKED,'protected_before':before,'protected_after':after}
write(REVIEW/'g3_ratio_codex_review_results.json',summary)
print(output.getvalue())
print(json.dumps({k:v for k,v in summary.items() if k not in {'suite_stdout','protected_before','protected_after'}},ensure_ascii=False,indent=2))
