"""Independent r2 closure review; no producer outputs are rewritten."""
import contextlib, copy, hashlib, io, json, runpy, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
SMOKE = ROOT/'claude methods/_m2_smoke'
HERE = SMOKE/'g3_ratio_analysis_20260909_r2'
REVIEW = Path(__file__).resolve().parent
BLOCKED=[]
def audit(event,args):
    if event in {'sqlite3.connect','subprocess.Popen','os.system'}:
        BLOCKED.append(event); raise RuntimeError('offline review prohibits '+event)
    if event in {'socket.connect','socket.bind','socket.getaddrinfo'}:
        endpoint=args[0] if event=='socket.getaddrinfo' else args[1]
        host=endpoint[0] if isinstance(endpoint,tuple) else endpoint
        if host not in {'127.0.0.1','::1','localhost'}:
            BLOCKED.append(event); raise RuntimeError('offline review prohibits external sockets')
sys.addaudithook(audit)
sys.dont_write_bytecode=True
sys.path[:0]=[str(HERE),str(SMOKE)]
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p): return json.loads(p.read_text(encoding='utf-8'))
def tree(): return {p.relative_to(ROOT).as_posix():sha(p) for p in SMOKE.rglob('*') if p.is_file() and '__pycache__' not in p.parts}
before=tree(); checks=[]
def expect(name,ok,detail=None): checks.append(dict(name=name,passed=bool(ok),detail=detail))
import smoke_capture as cap
import g3_ratio_analysis as g3
import basis_record as br
stdout=io.StringIO()
with cap.no_remote_connections('Codex r2 offline'),cap.db_guard('Codex r2 offline'),contextlib.redirect_stdout(stdout):
    try: runpy.run_path(str(HERE/'test_g3_ratio_analysis.py'),run_name='__main__'); suite_exit=0
    except SystemExit as e: suite_exit=e.code
with cap.no_remote_connections('Codex r2 offline'),cap.db_guard('Codex r2 offline'):
    stored=read(HERE/'results.json'); provenance=read(HERE/'PROVENANCE.json')
    manifest,extract,vendor=g3.load_inputs()
    fresh=g3.analyse(manifest,extract,vendor)
    expect('Claude focused suite passes',suite_exit==0)
    expect('all retained results reproduce',stored['results']==fresh)
    payload=dict(stored,results=fresh,documented_segments=g3.documented_470_row_segments(fresh))
    expect('Markdown report reproduces',g3.render_report(payload)==(HERE/'REPORT.md').read_text(encoding='utf-8'))
    expect('input file hashes recompute',all(sha(g3.DEFAULT_REVISION/n)==h for n,h in stored['inputs']['input_hashes'].items()))
    expect('code file hashes recompute',all(sha((HERE if (HERE/n).exists() else SMOKE)/n)==h for n,h in stored['code_hashes'].items()))
    expect('provenance output hashes recompute',all(sha(HERE/n)==h for n,h in provenance['output_hashes'].items()))
    expect('provenance input and code maps agree',provenance['inputs']==stored['inputs'] and provenance['code_hashes']==stored['code_hashes'])
    v=br.verify(g3.DEFAULT_REVISION)
    expect('basis verifier still verifies selected revision',not v['pins_stale'],v['deterministic_sha256'])
    for job,symbol,count in [('sh600011','SH600011',538),('bj920000','BJ920000',501),('sh000300','SH000300',538)]:
        b=fresh[job]; c=b['comparison']; refs={r['trade_date']:r for r in extract['rows'][symbol]}; vs={r['date']:r['close'] for r in vendor[job]['rows']}
        dates=sorted(set(refs)&set(vs)); ratios=[vs[d]/refs[d]['close'] for d in dates]
        expect(job+' independent ratio join',c['ratio']['series']==list(map(list,zip(dates,ratios))) and len(dates)==count)
        expect(job+' independent changes',[(x['from_date'],x['to_date'],x['change']) for x in c['ratio_changes']['records']]==[(dates[i],dates[i+1],ratios[i+1]-ratios[i]) for i in range(len(dates)-1)])
        expect(job+' metadata endpoint flags',all(x['source_changed']==(refs[x['from_date']]['source']!=refs[x['to_date']]['source']) and x['updated_at_changed']==(refs[x['from_date']]['updated_at']!=refs[x['to_date']]['updated_at']) for x in c['ratio_changes']['records']))
        expect(job+' usable count partition',c['compared_dates']==sum(s['compared_dates'] for s in b['segments']))
    # Public analyse path, modified copies only, covering both retained input sides.
    for side in ['vendor','reference']:
        for label,value in [('null',None),('true',True),('false',False),('numeric_string','12.3'),('nonnumeric','bad'),('nan',float('nan')),('inf',float('inf')),('negative_inf',-float('inf')),('zero',0),('negative',-1)]:
            ex=copy.deepcopy(extract); ve=copy.deepcopy(vendor); date=ex['rows']['SH600011'][1]['trade_date']
            rows=ex['rows']['SH600011'] if side=='reference' else ve['sh600011']['rows']; key='trade_date' if side=='reference' else 'date'
            next(r for r in rows if r[key]==date)['close']=value
            try:
                b=g3.analyse(manifest,ex,ve)['sh600011']; c=b['comparison']
                ok=c['matched_dates']==538 and c['compared_dates']==537 and date in [x['date'] for x in c['invalid_'+side+'_closes']] and sum(s['compared_dates'] for s in b['segments'])==537
                json.dumps(b,allow_nan=False)
                detail={'matched':c['matched_dates'],'usable':c['compared_dates']}
            except Exception as e: ok=False;detail=repr(e)
            expect(side+' '+label+' public invalid handling',ok,detail)
    def scenario(refs,vs): return g3.analyse({}, {'rows':{'SH600011':refs}}, {'sh600011':{'rows':vs}})['sh600011']
    dates=['2024-06-03','2024-06-04','2024-06-05','2024-06-06','2024-06-07']
    refs=[dict(trade_date=d,close=10.,source='A',updated_at='t1',adjustment_mode='qfq') for d in dates]
    vs=[dict(date=d,close=10.+i) for i,d in enumerate(dates)]
    # Three different skipped-date reasons in one consecutive usable pair.
    gaprefs=copy.deepcopy(refs);gapvs=copy.deepcopy(vs)
    gaprefs[2]['close']=None; gaprefs.pop(3);gapvs.pop(1)
    b=scenario(gaprefs,gapvs); record=b['comparison']['ratio_changes']['records'][0]
    expect('gap records preserve all three exclusion reasons',record['from_date']==dates[0] and record['to_date']==dates[4] and record['skipped_reference_only_dates']==[dates[1]] and record['skipped_matched_but_unusable']==[dates[2]] and record['skipped_vendor_only_dates']==[dates[3]] and not record['adjacent_with_no_skipped_dates'],record)
    # Endpoint labels can return to A after an intervening unusable B segment.
    hidden=copy.deepcopy(refs[:3]); hidden[1].update(close=None,source='B',updated_at='t2')
    b=scenario(hidden,vs[:3]); r=b['comparison']['ratio_changes']['records'][0]
    expect('skipped-date round-trip metadata boundaries remain flagged',r['metadata_boundary'] is True,{'record':r,'known_boundaries':b['boundaries']['source_or_fetch_time_boundaries']})
    prior=read(REVIEW/'g3_ratio_codex_review_results.json')['protected_after']
    drift=[p for p,h in prior.items() if not (ROOT/p).is_file() or sha(ROOT/p)!=h]
    expect('prior smoke and original G3 delivery preserved',not drift,drift)
after=tree();expect('all smoke files preserved during review',before==after,len(before))
summary=dict(suite_exit=suite_exit,suite_stdout=stdout.getvalue(),checks=checks,total=len(checks),passed=sum(c['passed'] for c in checks),blocked_operations=BLOCKED,protected_before=before,protected_after=after)
(REVIEW/'g3_ratio_codex_review_r2_results.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
print(stdout.getvalue());print(json.dumps({k:v for k,v in summary.items() if k not in {'suite_stdout','protected_before','protected_after','checks'}},indent=2))
print(json.dumps([c for c in checks if not c['passed']],indent=2))
