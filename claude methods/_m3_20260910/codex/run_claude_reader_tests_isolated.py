"""Run the delivered M3-02 tests in a fresh Codex-only synthetic fixture scope.

The original module/test files remain unchanged. Only their synthetic scratch and
output directory constants are relocated in memory, so the independent run cannot
delete or overwrite Claude's ongoing fixtures. Real source/policy constants remain
fixed. Audit hooks independently deny SQLite outside the new scratch scope, network,
child processes and all filesystem mutations outside this execution directory.
"""
import contextlib
from datetime import datetime, timezone
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import sys
import unittest
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
TEST = ROOT/'backend/tests/test_m3_frozen_reader.py'
READER = ROOT/'backend/app/research/m3_frozen_reader.py'
LABELS = ROOT/'backend/app/research/m3_labels.py'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    out = Path(sys.argv[1]).resolve()
    if out.parent != HERE or out.exists():
        raise SystemExit('new direct Codex execution directory required')
    pins = {str(p):sha(p) for p in (TEST,READER,LABELS,Path(__file__))}
    out.mkdir()
    for p in (TEST,READER,Path(__file__)):
        (out/p.name).write_bytes(p.read_bytes())
    synthetic_root = out/'synthetic'
    fixture_root = synthetic_root/'scratch'
    denied, connections = [], []

    def inside(path, scope=out):
        return isinstance(path,(str,os.PathLike)) and Path(path).resolve().is_relative_to(scope)

    def deny(event):
        denied.append(event)
        raise PermissionError('Independent reader test isolation: '+event)

    def audit(event,args):
        if event == 'sqlite3.connect':
            raw = args[0]
            text = str(raw)
            if text.startswith('file:'):
                path = unquote(urlsplit(text).path)
                if len(path)>3 and path[0]=='/' and path[2]==':':
                    path=path[1:]
            else:
                path=raw
            if not inside(path,fixture_root):
                deny('sqlite_outside_fixture_scope')
            connections.append(text)
        if event.startswith('socket.') or event in {'subprocess.Popen','os.system','os.startfile','os.spawn','os.exec','os.posix_spawn'}:
            deny(event)
        if event == 'open':
            path,mode,flags=args
            writing=(isinstance(mode,str) and any(c in mode for c in 'wax+')) or bool(flags & (os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC|os.O_APPEND))
            if writing and not inside(path):
                deny('write_outside_execution')
        if event in {'os.remove','os.rmdir','os.mkdir'} and not inside(args[0]):
            deny(event)
        if event=='os.rename' and not (inside(args[0]) and inside(args[1])):
            deny(event)
        if event in {'os.link','os.symlink'}:
            deny(event)

    sys.dont_write_bytecode=True
    sys.addaudithook(audit)
    stdout,stderr=io.StringIO(),io.StringIO()
    success=False
    executed=failures=errors=0
    with contextlib.redirect_stdout(stdout),contextlib.redirect_stderr(stderr):
        try:
            spec=importlib.util.spec_from_file_location('claude_reader_tests_isolated',TEST)
            suite_module=importlib.util.module_from_spec(spec)
            sys.modules[spec.name]=suite_module
            spec.loader.exec_module(suite_module)
            suite_module.SCRATCH=fixture_root/'test_fixtures'
            suite_module.r.CLAUDE_02_SCOPE=synthetic_root
            suite_module.r.SYNTHETIC_SCRATCH_SCOPE=fixture_root
            suite_module.r.OUTPUT_SCOPES=(synthetic_root/'runs',fixture_root)
            suite=unittest.defaultTestLoader.loadTestsFromModule(suite_module)
            result=unittest.TextTestRunner(stream=stderr,verbosity=2).run(suite)
            executed,failures,errors=result.testsRun,len(result.failures),len(result.errors)
            success=result.wasSuccessful() and not denied
        except Exception:
            import traceback
            traceback.print_exc()
    (out/'stdout.txt').write_text(stdout.getvalue(),encoding='utf-8')
    (out/'stderr.txt').write_text(stderr.getvalue(),encoding='utf-8')
    after={p:sha(Path(p)) for p in pins}
    if after!=pins:
        success=False
    receipt=dict(schema='m3.codex.claude_reader_tests_isolated.v1',checked_at_utc=datetime.now(timezone.utc).isoformat(),
        passed=success,tests_run=executed,failures=failures,errors=errors,
        pins_before=pins,pins_after=after,input_files_unchanged=after==pins,
        relocation='Only test.SCRATCH and reader synthetic/output scope constants relocated in memory; original sources and real/policy configuration unchanged.',
        sqlite_connections=connections,production_sqlite_connections=0,real_candidate_sqlite_connections=0,
        denied_events=denied,stdout_sha256=sha(out/'stdout.txt'),stderr_sha256=sha(out/'stderr.txt'),
        write_root=str(out),synthetic_fixture_scope=str(fixture_root),actual_case_reviews=0)
    (out/'execution.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in receipt.items() if k not in ('sqlite_connections','pins_after')},ensure_ascii=False))
    return 0 if success else 1


if __name__=='__main__':
    raise SystemExit(main())
