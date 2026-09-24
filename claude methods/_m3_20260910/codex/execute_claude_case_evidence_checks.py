"""Independently execute the case evidence checker with output-only relocation."""
import contextlib,hashlib,importlib.util,json,os,sys
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];HERE=Path(__file__).resolve().parent
SOURCE=ROOT/'claude methods/_m3_20260910/claude_03/tools/show_case_evidence.py'
OUT=HERE/'claude_case_evidence_checks_01'
assert not OUT.exists();OUT.mkdir()
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
before=sha(SOURCE);(OUT/'source.py').write_bytes(SOURCE.read_bytes());denied=[]
def audit(event,args):
 bad=event=='sqlite3.connect' or event.startswith('socket.') or event in {'subprocess.Popen','os.system','os.startfile','os.exec','os.spawn','os.posix_spawn','os.link','os.symlink'}
 if event=='open':
  p,mode,flags=args;writing=(isinstance(mode,str) and any(c in mode for c in 'wax+')) or bool(flags & (os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC|os.O_APPEND))
  if writing and not (isinstance(p,(str,os.PathLike)) and Path(p).resolve().is_relative_to(OUT)):bad=True
 if event in {'os.mkdir','os.remove','os.rmdir'} and not Path(args[0]).resolve().is_relative_to(OUT):bad=True
 if event=='os.rename' and not all(Path(p).resolve().is_relative_to(OUT) for p in args[:2]):bad=True
 if bad:denied.append(event);raise PermissionError(event)
sys.addaudithook(audit);sys.dont_write_bytecode=True
spec=importlib.util.spec_from_file_location('claude_case_check_review',SOURCE);mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
mod.LOG=OUT/'evidence_inspection_log.jsonl';mod.DOSSIERS=OUT/'dossiers'
sys.argv=[str(SOURCE)]+[f'C{i:03}' for i in range(1,33)]+[f'D{i:03}' for i in range(1,9)]
with (OUT/'stdout.txt').open('w',encoding='utf-8') as f,contextlib.redirect_stdout(f):rc=mod.main()
events=[json.loads(x) for x in mod.LOG.read_text('utf-8').splitlines()];assert len(events)==40
problems=[(e['case_id'],e['problems']) for e in events if e['problems']]
assert sha(SOURCE)==before
result={'passed':rc==0 and not problems and not denied,'recorded_at_utc':datetime.now(timezone.utc).isoformat(),'source':str(SOURCE),'source_sha256':before,'dossiers_checked':40,'cores_checked_with_prefix_occurrences':sum(e['cores_verified'] for e in events),'problems':problems,'denied_events':denied,'sqlite_connections':0,'network_requests':0,'source_preserved':True,'relocations':'LOG and DOSSIERS only, in memory, to fresh Codex output directory; evidence/policy/source constants unchanged','actual_agent_reviews_created':0,'not_an_individual_review':True}
(OUT/'execution.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(result,ensure_ascii=False));assert result['passed']
