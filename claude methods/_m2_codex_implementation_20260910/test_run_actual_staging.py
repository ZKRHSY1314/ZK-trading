"""Bounded unit and subprocess audit tests; no actual staging execution."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from urllib.parse import quote

import run_actual_staging as runner


class BoundaryTests(unittest.TestCase):
    def setUp(self):
        self.target = runner.HERE / "staging_runs/integration_test_dummy/run_test/test space.sqlite3"
        self.boundary = runner.AuditBoundary([self.target])

    def test_encoded_absolute_candidate_and_readonly_archive_allowed(self):
        for mode in ("ro", "rw"):
            uri = "file:" + quote(self.target.as_posix(), safe="/:") + "?mode=" + mode
            self.assertEqual(self.boundary.sqlite_path(uri), str(self.target.resolve()))
        archive = runner.ARCHIVES["history"]
        self.assertEqual(self.boundary.sqlite_path("file:" + archive.as_posix() + "?mode=ro"), str(archive.resolve()))
        self.assertEqual(self.boundary.sqlite_path("file::memory:"), "memory")

    def test_production_unc_relative_implicit_and_duplicate_modes_denied(self):
        candidate = self.target.as_posix()
        cases = [str(self.target), "file:relative.sqlite3?mode=rw", "file://server/share/x?mode=ro",
                 "file:" + candidate + "?mode=ro&mode=rw", "file:" + candidate + "?mode=ro&cache=shared",
                 "file:" + candidate + "?mode=rwc", "file:" + candidate + "?mode=ro#x",
                 "file:" + (runner.PROJECT / "trading_local.sqlite3").as_posix() + "?mode=ro",
                 "file:" + runner.ARCHIVES["history"].as_posix() + "?mode=rw"]
        for uri in cases:
            with self.subTest(uri=uri), self.assertRaises((runner.IntegrationError, ValueError)):
                self.boundary.sqlite_path(uri)

    def test_attach_only_readonly_allowlisted_files(self):
        with self.assertRaises(runner.IntegrationError):
            self.boundary.sqlite_path("file:" + self.target.as_posix() + "?mode=rw", attach=True)
        with self.assertRaises(runner.IntegrationError):
            self.boundary.sqlite_path("file::memory:", attach=True)

    def test_real_audit_hook_blocks_attach_connect_socket_and_process(self):
        # Isolate irreversible sys.addaudithook state in a child process. The
        # denied production path never reaches sqlite3's native connection open.
        with tempfile.TemporaryDirectory(prefix="integration_test_", dir=runner.HERE) as temp:
            path = Path(temp)
            self.assertEqual(path.resolve().parent, runner.HERE.resolve())
            source = r'''
import json,sqlite3,socket,subprocess,sys
from pathlib import Path
import run_actual_staging as r
p=Path(sys.argv[1])/'synthetic.sqlite3'
connection=sqlite3.connect(p)
connection.execute('CREATE TABLE fixture (id INTEGER)')
connection.close()
b=r.AuditBoundary([p]);b.install()
memory=sqlite3.connect('file::memory:',uri=True)
memory.execute('ATTACH ? AS fixture',('file:'+p.as_posix()+'?mode=ro',))
assert memory.execute('SELECT COUNT(*) FROM fixture.fixture').fetchone()[0]==0
blocked=[]
for name,action in [
 ('attach',lambda:memory.execute('ATTACH ? AS bad',('file:'+str(r.PROJECT/'trading_local.sqlite3')+'?mode=ro',))),
 ('connect',lambda:sqlite3.connect('file:'+str(r.PROJECT/'trading_local.sqlite3')+'?mode=ro',uri=True)),
 ('socket',lambda:socket.socket()),
 ('process',lambda:subprocess.Popen([sys.executable,'-c','raise SystemExit(99)']))]:
 try: action()
 except (r.IntegrationError,sqlite3.DatabaseError):blocked.append(name)
memory.close()
assert blocked==['attach','connect','socket','process'],blocked
print(json.dumps({'blocked':blocked,'connections':b.connections,'attachments':b.attachments,'denials':b.denials}))
'''
            result = subprocess.run([sys.executable, "-X", "utf8", "-B", "-c", source, temp], cwd=runner.HERE,
                text=True, encoding="utf-8", capture_output=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            proof = json.loads(result.stdout)
            self.assertEqual(proof["blocked"], ["attach", "connect", "socket", "process"])
            self.assertEqual(proof["connections"], ["memory"])
            self.assertEqual(len(proof["attachments"]), 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
