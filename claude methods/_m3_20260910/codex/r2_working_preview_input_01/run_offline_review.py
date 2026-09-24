"""Run a statically reviewed M3-01 stdlib test file with side effects restricted.

No SQLite, network or child processes. Writes are confined to a new Codex receipt
directory. This harness is for the synthetic-only M3-01 task, not case extraction.
"""
import contextlib
from datetime import datetime, timezone
import hashlib
import io
import json
import os
from pathlib import Path
import runpy
import sys
import tempfile

HERE = Path(__file__).resolve().parent
PHASE = HERE.parent
ROOT = PHASE.parents[1]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    target = Path(sys.argv[1]).resolve(strict=True)
    output = Path(sys.argv[2]).resolve()
    allowed_targets = {ROOT / 'backend/tests/test_m3_labels.py', HERE / 'boundary_probe.py',
                       HERE / 'test_independent_contract.py', HERE / 'test_feature_oracle.py',
                       HERE / 'test_independent_r2.py'}
    if target not in allowed_targets or not output.is_relative_to(HERE) or output == HERE or output.exists():
        raise SystemExit('exact reviewed test file and new Codex output directory required')
    target_pin = sha(target)
    module = ROOT / 'backend/app/research/m3_labels.py'
    module_pin = sha(module) if target.name != 'boundary_probe.py' else None
    output.mkdir()
    scratch = output / 'scratch'
    scratch.mkdir()
    tempfile.tempdir = str(scratch)
    denials = []

    def inside(path):
        return isinstance(path, (str, os.PathLike)) and Path(path).resolve().is_relative_to(output)

    def deny(event):
        denials.append(event)
        raise PermissionError('M3-01 offline review blocked: ' + event)

    def audit(event, args):
        if event == 'sqlite3.connect' or event.startswith('socket.') or event in {
            'subprocess.Popen', 'os.system', 'os.startfile', 'os.posix_spawn', 'os.spawn', 'os.exec'}:
            deny(event)
        if event == 'open':
            path, mode, flags = args
            writing = (isinstance(mode, str) and any(c in mode for c in 'wax+')) or bool(
                flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND))
            if writing and not inside(path):
                deny('open_write_outside_output')
        if event in {'os.remove', 'os.rmdir', 'os.mkdir'} and not inside(args[0]):
            deny(event + '_outside_output')
        if event == 'os.rename' and not (inside(args[0]) and inside(args[1])):
            deny('rename_outside_output')
        if event in {'os.link', 'os.symlink'}:
            deny(event)

    sys.addaudithook(audit)
    stdout, stderr = io.StringIO(), io.StringIO()
    sys.argv = [str(target)]
    code = 0
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        try:
            runpy.run_path(str(target), run_name='__main__')
        except SystemExit as exc:
            code = 0 if exc.code is None else exc.code if isinstance(exc.code, int) else 1
        except Exception:
            import traceback
            traceback.print_exc()
            code = 1
    (output / 'stdout.txt').write_text(stdout.getvalue(), encoding='utf-8')
    (output / 'stderr.txt').write_text(stderr.getvalue(), encoding='utf-8')
    assert sha(target) == target_pin, 'test source changed during execution'
    assert module_pin is None or sha(module) == module_pin, 'label module changed during execution'
    receipt = dict(schema='m3.offline_review_execution.v1', checked_at_utc=datetime.now(timezone.utc).isoformat(),
        target=str(target), target_sha256=target_pin, producer_sha256=sha(__file__), exit_code=code,
        module_path=str(module) if module_pin else None, module_sha256=module_pin,
        denied_events=denials, sqlite_connections_allowed=0, network_allowed=False,
        subprocesses_allowed=False, write_root=str(output),
        stdout_sha256=sha(output / 'stdout.txt'), stderr_sha256=sha(output / 'stderr.txt'))
    (output / 'execution.json').write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(receipt, ensure_ascii=False))
    return code


if __name__ == '__main__':
    raise SystemExit(main())
