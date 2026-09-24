"""Read-only isolated replay; outputs are Codex-owned, never Claude delivery artifacts."""
from pathlib import Path
import json, sys, io, unittest, importlib.util, hashlib
from datetime import datetime, timezone
ROOT=Path(__file__).resolve().parents[3]
OUT=Path(__file__).resolve().parent/'portfolio_review_03'
paths=[ROOT/'backend/app/research/m4_execution.py',ROOT/'backend/app/research/m4_portfolio.py',ROOT/'backend/tests/test_m4_portfolio.py']
before={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
denials=[]
def guard(event,args):
    denied=event.startswith(('sqlite3.','socket.','subprocess.')) or event in {'os.system','os.exec','os.posix_spawn','os.remove','os.rename','os.rmdir','os.mkdir'}
    if event=='open':
        p,mode,flags=args
        if (isinstance(mode,str) and any(c in mode for c in 'wax+')) or (isinstance(flags,int) and flags & (1|2|64|512|1024)):
            denied=not isinstance(p,(str,bytes)) or not Path(p).resolve().is_relative_to(OUT.resolve())
    if denied:
        denials.append(event);raise RuntimeError('Codex guard denied '+event)
sys.addaudithook(guard)
spec=importlib.util.spec_from_file_location('codex_portfolio_delivery_suite',paths[2])
t=importlib.util.module_from_spec(spec);sys.modules[spec.name]=t;spec.loader.exec_module(t)
stream=io.StringIO();result=unittest.TextTestRunner(stream=stream,verbosity=2).run(unittest.defaultTestLoader.loadTestsFromModule(t))
(OUT/'delivery_suite_stdout.txt').write_text(stream.getvalue(),encoding='utf-8')
unchanged=all(hashlib.sha256(p.read_bytes()).hexdigest()==before[str(p)] for p in paths)
receipt={'observed_at_utc':datetime.now(timezone.utc).isoformat(),'command':sys.orig_argv,'source_hashes':before,'source_unchanged':unchanged,'tests':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),'skipped':len(result.skipped),'successful':result.wasSuccessful(),'guard_denials':denials,'app_imported':any(n=='app' or n.startswith('app.') for n in sys.modules),'conftest_imported':any('conftest' in n for n in sys.modules),'synthetic_only':True,'live_trading_enabled':False,'review_only':True,'accepted':False}
(OUT/'delivery_suite_receipt.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(receipt,ensure_ascii=False,indent=2))
sys.exit(0 if result.wasSuccessful() and unchanged and not denials else 1)
