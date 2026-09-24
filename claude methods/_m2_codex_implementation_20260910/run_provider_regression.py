"""Existing provider regression with no real network or production SQLite access."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import os
import socket
import sys
import tempfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
out = HERE / 'test_runtime' / datetime.now(timezone.utc).strftime('provider_%Y%m%dT%H%M%S%fZ')
out.mkdir(parents=True, exist_ok=False)
tempfile.tempdir = str(out)
os.environ['DATABASE_PATH'] = str(out / 'bootstrap.sqlite3')
os.environ['ENABLE_LIVE_TRADING'] = 'false'
os.environ['PYTEST_DISABLE_PLUGIN_AUTOLOAD'] = '1'
os.environ['PYTHONDONTWRITEBYTECODE'] = '1'
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT / 'backend'))
events = {'sqlite_connections': 0, 'network_attempts_blocked': 0,
          'production_database_attempts_blocked': 0, 'stdlib_socketpair_connections': 0}
socketpair_code = getattr(socket, '_fallback_socketpair').__code__

def audit(event, args):
    if event == 'socket.connect':
        caller = sys._getframe(1)
        if (caller.f_code is socketpair_code and args[0] is caller.f_locals.get('csock')
                and args[1] == (caller.f_locals.get('addr'), caller.f_locals.get('port'))
                and args[1][0] in ('127.0.0.1', '::1')):
            # Windows asyncio self-pipe connects to its newly bound socket pair.
            # This exact stdlib call is local IPC; arbitrary loopback is denied.
            events['stdlib_socketpair_connections'] += 1
            return
        events['network_attempts_blocked'] += 1
        raise RuntimeError('real network disabled in isolated provider regression')
    if event == 'sqlite3.connect':
        target = str(args[0])
        if target != ':memory:' and (target.startswith('file:') or
                not Path(target).resolve().is_relative_to(out.resolve())):
            events['production_database_attempts_blocked'] += 1
            raise RuntimeError('database outside isolated regression directory')
        events['sqlite_connections'] += 1

sys.addaudithook(audit)
os.chdir(ROOT / 'backend')
import pytest
result = pytest.main(['-q', '-p', 'no:cacheprovider',
    '--basetemp', str(out / 'pytest'), 'tests/test_tonghuasun_provider.py'])
from app.config import settings
report = dict(exit_code=int(result), guards=events,
    live_trading_enabled=settings.enable_live_trading,
    production_database_access=False, actual_network_access=False,
    test_sha256=hashlib.sha256((ROOT/'backend/tests/test_tonghuasun_provider.py').read_bytes()).hexdigest(),
    provider_sha256=hashlib.sha256((ROOT/'backend/app/data/tonghuasun_provider.py').read_bytes()).hexdigest(),
    runner_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
(out/'result.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
print(json.dumps({'result': report, 'artifact': str(out/'result.json')}, ensure_ascii=True))
raise SystemExit(int(result) or int(settings.enable_live_trading) or
    int(bool(events['production_database_attempts_blocked'] or events['network_attempts_blocked'])))
